import os

from utils import my_keras_to_tensorflow as k2tf
from utils import my_utils

import numpy

def convert_keras_models_to_tf(model_root):
    from keras.models import load_model
    from keras import backend as K

    keras_models_dir = os.path.join(model_root, 'keras_models')

    tf_models_dir = os.path.join(model_root, 'tf_models')
    my_utils.create_dir_if_not_exist(tf_models_dir)

    model_names = ['autoencoder', 'decoder', 'encoder', 'energy_model', 'discrete_energy_model']

    K.clear_session()
    for model_name in model_names:
        model_path = os.path.join(keras_models_dir, model_name + '.hdf5')
        if os.path.exists(model_path):
            import keras.losses
            keras.losses.energy_loss = lambda x,y: x
            model = load_model(model_path)
            k2tf.save_keras_model_as_tf(model, os.path.join(tf_models_dir, model_name + '.pb'))
            K.clear_session()
