import tensorflow as tf
from tensorflow.keras.layers import (
    Conv2D,
    SeparableConv2D,
    DepthwiseConv2D,
    BatchNormalization,
    GlobalAveragePooling2D,
    Concatenate,
    Add,
    Lambda,
    ReLU
)

from coral_deeplab.layers import UpSampling2D


def inverted_res_block(inputs: tf.Tensor, project_channels: int,
                       block_num: int, expand_channels: int = 960,
                       expand: bool = False, skip: bool = False) -> tf.Tensor:
    """
    """
    block_name = f'block_{block_num}'
    x = inputs

    if expand:
        x = Conv2D(expand_channels, 1, padding='same', use_bias=False,
                   name=f'{block_name}_expand')(x)
        x = BatchNormalization(name=f'{block_name}_expand_bn')(x)
        x = ReLU(6, name=f'{block_name}_expand_relu')(x)

    # depthwise
    x = DepthwiseConv2D(3, padding='same', dilation_rate=2,
                        use_bias=False, name=f'{block_name}_depthwise')(x)
    x = BatchNormalization(name=f'{block_name}_depthwise_bn')(x)
    x = ReLU(6, name=f'{block_name}_depthwise_relu')(x)

    # project
    x = Conv2D(project_channels, 1, padding='same', use_bias=False,
               name=f'{block_name}_project')(x)
    x = BatchNormalization(name=f'{block_name}_project_bn')(x)

    if skip:
        x = Add(name=f'{block_name}_add')([x, inputs])

    return x


def deeplab_aspp_module(inputs: tf.Tensor, dilation_rates: list,
                        bn_epsilon: float) -> tf.Tensor:
    """
    """

    # aspp branch 0
    b0 = SeparableConv2D(256, 3, padding='same',
                         use_bias=False, name='aspp0')(inputs)
    b0 = BatchNormalization(epsilon=bn_epsilon, name='aspp0_bn')(b0)
    b0 = ReLU(name='aspp0_relu')(b0)

    # branches 1-3
    dilated_branches = []

    for i, dilation in enumerate(dilation_rates):
        lname = f'aspp{(i + 1) * 3}'
        bx = SeparableConv2D(256, 3, padding='same', dilation_rate=dilation,
                             use_bias=False, name=lname)(inputs)
        bx = BatchNormalization(epsilon=bn_epsilon, name=f'{lname}_bn')(bx)
        bx = ReLU(name=f'{lname}_relu')(bx)
        dilated_branches.append(bx)

    # branch 4
    _, *size, _ = tf.keras.backend.int_shape(inputs)
    b4 = GlobalAveragePooling2D(name='aspp4_pooling')(inputs)
    b4 = Lambda(lambda t: t[:, tf.newaxis, tf.newaxis, :])(b4)
    b4 = UpSampling2D(size=size, interpolation='bilinear')(b4)
    b4 = Conv2D(256, 1, padding='same', use_bias=False, name='aspp4')(b4)
    b4 = BatchNormalization(name='aspp4_bn', epsilon=bn_epsilon)(b4)
    b4 = ReLU(name='aspp4_relu')(b4)

    # concat and pointwise conv
    # TODO names
    x = Concatenate()([b0, *dilated_branches, b4])
    x = Conv2D(256, 1, padding='same', use_bias=False)(x)
    x = BatchNormalization(epsilon=bn_epsilon)(x)
    outputs = ReLU()(x)

    return outputs


def deeplab_decoder(inputs: tf.Tensor, skip_con: tf.Tensor,
                    n_classes: int, bn_epsilon: float) -> tf.Tensor:
    """
    Notes
    -----
    Using output stride 8
    """

    if n_classes > 50:
        print('Warning - model might not compile'
              ' due to upsampling of large tensors.'
              ' Consider decreasing number of'
              ' segmentation classes.')

    skip = Conv2D(48, 1, padding='same', use_bias=False,
                  name='project_0')(skip_con)
    skip = BatchNormalization(epsilon=bn_epsilon)(skip)
    skip = ReLU()(skip)

    aspp_up = UpSampling2D(size=(4, 4), interpolation='bilinear')(inputs)
    x = Concatenate()([aspp_up, skip])

    x = SeparableConv2D(256, 3, padding='same', use_bias=False)(x)
    x = BatchNormalization(epsilon=bn_epsilon)(x)
    x = ReLU()(x)

    x = SeparableConv2D(256, 3, padding='same', use_bias=False)(x)
    x = BatchNormalization(epsilon=bn_epsilon)(x)
    x = ReLU()(x)

    outputs = SeparableConv2D(n_classes, 3, padding='same', use_bias=False)(x)
    outputs = UpSampling2D(size=(4, 4), interpolation='bilinear')(outputs)

    return outputs
