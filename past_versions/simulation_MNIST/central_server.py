from neural_network import Neural_Network
from vehicle import Vehicle
import numpy as np
import yaml
import mxnet as mx
from mxnet import gluon, nd
from mxnet.gluon import nn


file = open('config.yml', 'r')
cfg = yaml.load(file, Loader=yaml.FullLoader)

class Central_Server:
    """
    Central Server object for Car ML Simulator.
    Attributes:
    - model
    - accumulative_gradients
    """
    def __init__(self, ctx, rsu_list):
        self.net = gluon.nn.Sequential()
        with self.net.name_scope():
            self.net.add(nn.Dense(128, activation='relu'))
            self.net.add(nn.Dense(64, activation='relu'))
            self.net.add(nn.Dense(10))
        self.net.initialize(mx.init.Xavier(), ctx=ctx, force_reinit=True)

        self.accumulative_gradients = []

    # Update the model with its accumulative gradients
    # Used for batch gradient descent
    def update_model(self):
        if len(self.accumulative_gradients) >= 10:
            param_list = [nd.concat(*[xx.reshape((-1, 1)) for xx in x], dim=0) for x in self.accumulative_gradients]
            mean_nd = nd.mean(nd.concat(*param_list, dim=1), axis=-1)
            idx = 0
            for j, (param) in enumerate(self.net.collect_params().values()):
                if param.grad_req != 'null':
                    # mapping back to the collection of ndarray
                    # directly update model
                    lr = cfg['neural_network']['learning_rate']
                    param.set_data(param.data() - lr * mean_nd[idx:(idx+param.data().size)].reshape(param.data().shape))
                    idx += param.data().size
            self.accumulative_gradients = []


class Simulation:
    """
    Simulation object for Car ML Simulator. Stores all the global variables.
    Attributes:
    - FCD_file
    - vehicle_dict
    - rsu_list
    - dataset
    """
    def __init__(self, FCD_file, vehicle_dict: dict, rsu_list: list, central_server, training_set, val_train_data, val_test_data):
        self.FCD_file = FCD_file
        self.vehicle_dict = vehicle_dict
        self.rsu_list = rsu_list
        self.central_server = central_server
        self.num_epoch = 0
        self.training_data = []
        self.epoch_loss = mx.metric.CrossEntropy()
        self.epoch_accuracy = mx.metric.Accuracy()
        self.training_set = training_set
        self.val_train_data = val_train_data
        self.val_test_data = val_test_data
       
    def add_into_vehicle_dict(self, vehicle):
        self.vehicle_dict[vehicle.attrib['id']] = Vehicle(vehicle.attrib['id'])

    def print_accuracy(self):
        self.epoch_accuracy.reset()
        self.epoch_loss.reset()
        print("start")
        # accuracy on testing data
        for i, (data, label) in enumerate(self.val_test_data):
            outputs = self.central_server.net(data)
            # this following line takes EXTREMELY LONG to run
            self.epoch_accuracy.update(label, outputs)
        # cross entropy on training data
        for i, (data, label) in enumerate(self.val_train_data):
            outputs = self.central_server.net(data)
            self.epoch_loss.update(label, nd.softmax(outputs))

        _, accu = self.epoch_accuracy.get()
        _, loss = self.epoch_loss.get()
        # loss = 0
        # accu = 0
        print("Epoch {:03d}: Loss: {:03f}, Accuracy: {:03f}".format(self.num_epoch,
                                                                    loss,
                                                                    accu))
                                                                
    def new_epoch(self):
        self.num_epoch += 1
        for i, (data, label) in enumerate(self.training_set):
            self.training_data.append((data, label))

