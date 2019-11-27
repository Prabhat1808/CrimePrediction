# -*- coding: utf-8 -*-
"""TrainingModels.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1494FDu9fsfA0tcO6swyz6hVi2wV-3RB2
"""

# from google.colab import drive
# drive.mount('/content/gdrive')

# LSTM and RNN code derived from the following github repo: https://github.com/TobiasLee/Text-Classification

import numpy as np
import pandas as pd
import time
import pickle

from tensorflow.contrib.rnn import BasicLSTMCell
from tensorflow.python.ops.rnn import bidirectional_dynamic_rnn as bi_rnn
import tensorflow as tf
tf.disable_v2_behavior()

from sklearn.metrics import f1_score,accuracy_score
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split

# (365x78x4) matrices, as mentioned in the preprocessing steps

input311File = 'matrices311'
inputCrimeFile = 'matricesCR'

with open(inputCrimeFile, 'rb') as pickle_file:
    anomaly = pickle.load(pickle_file)

with open(inputCrimeFile,'rb') as pickle_file:
    content = pickle.load(pickle_file)

# Preprocessing the crime and anomaly matrices
# To remove the 0th row of each of the (78x4) matrices
# ,since they contain data events for which geographical data was not available
# as mentioned in the preprocessing code

dat = []
dat2 = []
for i in range(len(content)):
  a = []
  b = []
  for j in range(77):
    a.extend(content[i][j+1])
    b.extend(anomaly[i][j+1])
    # print(a)
  dat.append(a)
  dat2.append(b)

inp = np.array(dat)
inp1 = np.where(inp>0,1,0)inp = np.array(dat)
inp1 = np.where(inp>0,1,0)
inpA = np.array(dat2)
inpA = np.array(dat2)

# Train test split for the above data

size = int(len(inp)*0.8)
x_train = inp[:size]
y_train = inp1[:size]
x_test = inp[size:]
y_test = inp1[size:]
x_train2 = inpA[:size]
x_test2 = inpA[size:]

def attention(inputs, attention_size, time_major=False, return_alphas=False):
    """
    Attention mechanism layer which reduces RNN/Bi-RNN outputs with Attention vector.
    The idea was proposed in the article by Z. Yang et al., "Hierarchical Attention Networks
     for Document Classification", 2016: http://www.aclweb.org/anthology/N16-1174.
    Variables notation is also inherited from the article
    Args:
        inputs: The Attention inputs.
            Matches outputs of RNN/Bi-RNN layer (not final state):
                In case of RNN, this must be RNN outputs `Tensor`:
                    If time_major == False (default), this must be a tensor of shape:
                        `[batch_size, max_time, cell.output_size]`.
                    If time_major == True, this must be a tensor of shape:
                        `[max_time, batch_size, cell.output_size]`.
                In case of Bidirectional RNN, this must be a tuple (outputs_fw, outputs_bw) containing the forward and
                the backward RNN outputs `Tensor`.
                    If time_major == False (default),
                        outputs_fw is a `Tensor` shaped:
                        `[batch_size, max_time, cell_fw.output_size]`
                        and outputs_bw is a `Tensor` shaped:
                        `[batch_size, max_time, cell_bw.output_size]`.
                    If time_major == True,
                        outputs_fw is a `Tensor` shaped:
                        `[max_time, batch_size, cell_fw.output_size]`
                        and outputs_bw is a `Tensor` shaped:
                        `[max_time, batch_size, cell_bw.output_size]`.
        attention_size: Linear size of the Attention weights.
        time_major: The shape format of the `inputs` Tensors.
            If true, these `Tensors` must be shaped `[max_time, batch_size, depth]`.
            If false, these `Tensors` must be shaped `[batch_size, max_time, depth]`.
            Using `time_major = True` is a bit more efficient because it avoids
            transposes at the beginning and end of the RNN calculation.  However,
            most TensorFlow data is batch-major, so by default this function
            accepts input and emits output in batch-major form.
        return_alphas: Whether to return attention coefficients variable along with layer's output.
            Used for visualization purpose.
    Returns:
        The Attention output `Tensor`.
        In case of RNN, this will be a `Tensor` shaped:
            `[batch_size, cell.output_size]`.
        In case of Bidirectional RNN, this will be a `Tensor` shaped:
            `[batch_size, cell_fw.output_size + cell_bw.output_size]`.
    """

    if isinstance(inputs, tuple):
        # In case of Bi-RNN, concatenate the forward and the backward RNN outputs.
        inputs = tf.concat(inputs, 2)

    if time_major:
        # (T,B,D) => (B,T,D)
        inputs = tf.array_ops.transpose(inputs, [1, 0, 2])

    hidden_size = inputs.shape[2].value  # D value - hidden size of the RNN layer

    # Trainable parameters
    w_omega = tf.Variable(tf.random_normal([hidden_size, attention_size], stddev=0.1))
    b_omega = tf.Variable(tf.random_normal([attention_size], stddev=0.1))
    u_omega = tf.Variable(tf.random_normal([attention_size], stddev=0.1))

    with tf.name_scope('v'):
        # Applying fully connected layer with non-linear activation to each of the B*T timestamps;
        #  the shape of `v` is (B,T,D)*(D,A)=(B,T,A), where A=attention_size
        v = tf.tanh(tf.tensordot(inputs, w_omega, axes=1) + b_omega)

    # For each of the timestamps its vector of size A from `v` is reduced with `u` vector
    vu = tf.tensordot(v, u_omega, axes=1, name='vu')  # (B,T) shape
    alphas = tf.nn.softmax(vu, name='alphas')  # (B,T) shape

    # Output of (Bi-)RNN is reduced with attention vector; the result has (B,D) shape
    output = tf.reduce_sum(inputs * tf.expand_dims(alphas, -1), 1)

    if not return_alphas:
        return output
    else:
        return output, alphas

def split_dataset(x_test, y_test, dev_ratio):
    """split test dataset to test and dev set with ratio """
    test_size = len(x_test)
    print(test_size)
    dev_size = (int)(test_size * dev_ratio)
    print(dev_size)
    x_dev = x_test[:dev_size]
    x_test = x_test[dev_size:]
    y_dev = y_test[:dev_size]
    y_test = y_test[dev_size:]
    return x_test, x_dev, y_test, y_dev, dev_size, test_size - dev_size


def fill_feed_dict(data_X, data_Y, batch_size):
    """Generator to yield batches"""
    # Shuffle data first.
    shuffled_X, shuffled_Y = shuffle(data_X, data_Y)
    # print("before shuffle: ", data_Y[:10])
    # print(data_X.shape[0])
    # perm = np.random.permutation(data_X.shape[0])
    # data_X = data_X[perm]
    # shuffled_Y = data_Y[perm]
    # print("after shuffle: ", shuffled_Y[:10])
    for idx in range(data_X.shape[0] // batch_size):
        x_batch = shuffled_X[batch_size * idx: batch_size * (idx + 1)]
        y_batch = shuffled_Y[batch_size * idx: batch_size * (idx + 1)]
        yield x_batch, y_batch

# Hyperparameters

MAX_DOCUMENT_LENGTH = 128
EMBEDDING_SIZE = 128
HIDDEN_SIZE = 64
ATTENTION_SIZE = 64
lr = 5e-4
learning_rate=0.001
hidden_dim = 250
BATCH_SIZE = 4
KEEP_PROB = 1.0
LAMBDA = 0.0001
MAX_LABEL = 77*4
epochs = 10
latent_dim = 8
# n_batches = 1
timeSize = 10
max_len=10

def multi_label_hot(prediction, threshold=0.5):
    prediction = tf.cast(prediction, tf.float32)
    threshold = float(threshold)
    return tf.cast(tf.greater(prediction, threshold), tf.int64)

def get_metrics(labels_tensor, one_hot_prediction, num_classes):
    metrics = {}
    with tf.variable_scope("metrics"):
        for scope in ["train", "val"]:
            with tf.variable_scope(scope):
                with tf.variable_scope("accuracy"):
                    accuracy, accuracy_update = tf.metrics.accuracy(
                        tf.cast(one_hot_prediction, tf.int32),
                        labels_tensor,
                    )
                metrics[scope] = {
                    "accuracy": accuracy,
                    "updates": tf.group(accuracy_update),
                }
    return metrics

# Bi-LSTM based architecture with Attention
# https://github.com/TobiasLee/Text-Classification

tf.reset_default_graph()
batch_x = tf.placeholder(tf.float32, [None,timeSize,MAX_LABEL])
anomaly_x = tf.placeholder(tf.float32, [None,timeSize,MAX_LABEL])
batch_y = tf.placeholder(tf.float32, [None, MAX_LABEL])
keep_prob = tf.placeholder(tf.float32)

rnn_outputs1, _ = bi_rnn(BasicLSTMCell(HIDDEN_SIZE),
                        BasicLSTMCell(HIDDEN_SIZE),
                        inputs=batch_x, dtype=tf.float32,scope='BLSTM_1')
fw_outputs1, bw_outputs1 = rnn_outputs1

rnn_outputs2, _ = bi_rnn(BasicLSTMCell(HIDDEN_SIZE),
                        BasicLSTMCell(HIDDEN_SIZE),
                        inputs=anomaly_x, dtype=tf.float32,scope='BLSTM_2')
fw_outputs2, bw_outputs2 = rnn_outputs2

# weights for balance outs
weight_out = tf.Variable(tf.truncated_normal([4], stddev=0.1))
weight_soft = tf.nn.softmax(weight_out)

inputAdd = weight_soft[0]*fw_outputs1 + weight_soft[1]**fw_outputs2 + weight_soft[2]*bw_outputs1 + weight_soft[3]*bw_outputs2
print(batch_x.shape)
print(inputAdd.shape)
rnn_outputs, _ = bi_rnn(BasicLSTMCell(HIDDEN_SIZE),
                        BasicLSTMCell(HIDDEN_SIZE),
                        inputs=inputAdd, dtype=tf.float32,scope='BLSTM_3')
fw_outputs, bw_outputs = rnn_outputs

# # Attention
# attention_output, alphas = attention(rnn_outputs, ATTENTION_SIZE, return_alphas=True)
# drop = tf.nn.dropout(attention_output, keep_prob)
# shape = drop.get_shape()
# print(shape)
# # Fully connected layer（dense layer)
# W = tf.Variable(tf.truncated_normal([shape[1].value, MAX_LABEL], stddev=0.1))
# b = tf.Variable(tf.constant(0., shape=[MAX_LABEL]))
# y_hat = tf.nn.xw_plus_b(drop, W, b)
W = tf.Variable(tf.random_normal([HIDDEN_SIZE], stddev=0.1))
H = fw_outputs + bw_outputs  # (batch_size, seq_len, HIDDEN_SIZE)
M = tf.tanh(H)  # M = tanh(H)  (batch_size, seq_len, HIDDEN_SIZE)

alpha = tf.nn.softmax(tf.reshape(tf.matmul(tf.reshape(M, [-1, HIDDEN_SIZE]),
                                                tf.reshape(W, [-1, 1])),
                                      (-1, timeSize )))  # batch_size x seq_len

print(alpha.shape)
r = tf.matmul(tf.transpose(H, [0, 2, 1]),
              tf.reshape(alpha, [-1, timeSize, 1]))
r = tf.squeeze(r)
h_star = tf.tanh(r)  # (batch , HIDDEN_SIZE

h_drop = tf.nn.dropout(h_star, keep_prob)
shape = h_drop.get_shape()
# print(h_star.shape)
# Fully connected layer（dense layer)
FC_W = tf.Variable(tf.truncated_normal([HIDDEN_SIZE, MAX_LABEL], stddev=0.1))
FC_b = tf.Variable(tf.constant(0., shape=[MAX_LABEL]))
y_hat2 = tf.nn.xw_plus_b(h_drop, FC_W, FC_b)
print(y_hat2.shape)
FC_W2 = tf.Variable(tf.truncated_normal([MAX_LABEL, MAX_LABEL], stddev=0.1))
FC_b2 = tf.Variable(tf.constant(0., shape=[MAX_LABEL]))
y_hat = tf.nn.xw_plus_b(y_hat2, FC_W2, FC_b2)

# ######## LOSS FUNCTIONS ######

# This loss function is used to predict the actual number of crime occurences, hence the L2 loss
loss =  tf.nn.l2_loss(y_hat-batch_y) +0.001*tf.nn.l2_loss(FC_W)+0.001*tf.nn.l2_loss(FC_W2) + 0.0001*tf.nn.l2_loss(W)

# Uncomment this, if you just want the binary predictions, not actual crime numbers
# loss =   tf.reduce_mean(tf.nn.sigmoid_cross_entropy_with_logits(logits=y_hat, labels=batch_y)) +0.001*tf.nn.l2_loss(FC_W)+0.001*tf.nn.l2_loss(FC_W2) + 0.0001*tf.nn.l2_loss(W)

# ######## LOSS FUNCTIONS ######

optimizer = tf.train.AdamOptimizer(learning_rate=lr).minimize(loss)

# optimization
# loss_to_minimize = loss
# tvars = tf.trainable_variables()
# gradients = tf.gradients(loss_to_minimize, tvars, aggregation_method=tf.AggregationMethod.EXPERIMENTAL_TREE)
# grads, global_norm = tf.clip_by_global_norm(gradients, 1.0)

# global_step = tf.Variable(0, name="global_step", trainable=False)
# optimizer = tf.train.AdamOptimizer(learning_rate=lr)
# train_op = optimizer.apply_gradients(zip(grads, tvars), global_step=global_step,
#                                                 name='train_step')

# Accuracy metric
# prediction = tf.argmax(tf.nn.softmax(y_hat), 1)
# accuracy = tf.reduce_mean(tf.cast(tf.equal(prediction, tf.argmax(batch_y, 1)), tf.float32))

prediction = tf.sigmoid(y_hat)
one_hot_prediction = multi_label_hot(prediction)

accuracy  =  get_metrics(batch_y,one_hot_prediction,77)

# RNN based architecture with Attention
# https://github.com/TobiasLee/Text-Classification

tf.reset_default_graph()
batch_x = tf.placeholder(tf.float32, [None,timeSize,MAX_LABEL])
anomaly_x = tf.placeholder(tf.float32, [None,timeSize,MAX_LABEL])
batch_y = tf.placeholder(tf.float32, [None, MAX_LABEL])
keep_prob = tf.placeholder(tf.float32)

rnn_outputs1, _ = tf.nn.dynamic_rnn(BasicLSTMCell(HIDDEN_SIZE),
                        inputs=batch_x, dtype=tf.float32,scope='BLSTM_1')

rnn_outputs2, _ = tf.nn.dynamic_rnn(BasicLSTMCell(HIDDEN_SIZE),
                        inputs=anomaly_x, dtype=tf.float32,scope='BLSTM_2')

# weights for balance-outs
weight_out = tf.Variable(tf.truncated_normal([2], stddev=0.1))
weight_soft = tf.nn.softmax(weight_out)

inputAdd = weight_soft[0]*rnn_outputs1 + weight_soft[1]*rnn_outputs2
print(batch_x.shape)
print(inputAdd.shape)
rnn_outputs, _ = tf.nn.dynamic_rnn(BasicLSTMCell(HIDDEN_SIZE),
                        inputs=inputAdd, dtype=tf.float32,scope='BLSTM_3')
# fw_outputs, bw_outputs = rnn_outputs


# # Attention
# attention_output, alphas = attention(rnn_outputs, ATTENTION_SIZE, return_alphas=True)
# drop = tf.nn.dropout(attention_output, keep_prob)
# shape = drop.get_shape()
# print(shape)
# # Fully connected layer（dense layer)
# W = tf.Variable(tf.truncated_normal([shape[1].value, MAX_LABEL], stddev=0.1))
# b = tf.Variable(tf.constant(0., shape=[MAX_LABEL]))
# y_hat = tf.nn.xw_plus_b(drop, W, b)
W = tf.Variable(tf.random_normal([HIDDEN_SIZE], stddev=0.1))
H = rnn_outputs  # (batch_size, seq_len, HIDDEN_SIZE)
M = tf.tanh(H)  # M = tanh(H)  (batch_size, seq_len, HIDDEN_SIZE)

alpha = tf.nn.softmax(tf.reshape(tf.matmul(tf.reshape(M, [-1, HIDDEN_SIZE]),
                                                tf.reshape(W, [-1, 1])),
                                      (-1, timeSize )))  # batch_size x seq_len

print(alpha.shape)
r = tf.matmul(tf.transpose(H, [0, 2, 1]),
              tf.reshape(alpha, [-1, timeSize, 1]))
r = tf.squeeze(r)
h_star = tf.tanh(r)  # (batch , HIDDEN_SIZE

h_drop = tf.nn.dropout(h_star, keep_prob)
shape = h_drop.get_shape()
# print(h_star.shape)
# Fully connected layer（dense layer)
FC_W = tf.Variable(tf.truncated_normal([HIDDEN_SIZE, MAX_LABEL], stddev=0.1))
FC_b = tf.Variable(tf.constant(0., shape=[MAX_LABEL]))
y_hat2 = tf.nn.xw_plus_b(h_drop, FC_W, FC_b)
print(y_hat2.shape)
FC_W2 = tf.Variable(tf.truncated_normal([MAX_LABEL, MAX_LABEL], stddev=0.1))
FC_b2 = tf.Variable(tf.constant(0., shape=[MAX_LABEL]))
y_hat = tf.nn.xw_plus_b(y_hat2, FC_W2, FC_b2)

loss =  tf.nn.l2_loss(y_hat-batch_y) +0.001*tf.nn.l2_loss(FC_W)+0.001*tf.nn.l2_loss(FC_W2) + 0.0001*tf.nn.l2_loss(W)
# loss =   tf.reduce_mean(tf.nn.sigmoid_cross_entropy_with_logits(logits=y_hat, labels=batch_y)) +0.001*tf.nn.l2_loss(FC_W)+0.001*tf.nn.l2_loss(FC_W2) + 0.0001*tf.nn.l2_loss(W)

optimizer = tf.train.AdamOptimizer(learning_rate=lr).minimize(loss)
prediction = tf.sigmoid(y_hat)
one_hot_prediction = multi_label_hot(prediction)

accuracy  =  get_metrics(batch_y,one_hot_prediction,77)

saver = tf.train.Saver()
!mkdir checkpointDir

# Model Parameters
slim = tf.contrib.slim
sess=tf.Session()
sess.run(tf.global_variables_initializer())
sess.run(tf.local_variables_initializer())
def model_summary():
    model_vars = tf.trainable_variables()
    slim.model_analyzer.analyze_vars(model_vars, print_info=True)
    
model_summary()

# To store training and test results for visualization

tr = []
ts = []

#sess.run(tf.global_variables_initializer())
print("Initialized! ")
target_names = ['a','b','c','d']
print("Start trainning")
start = time.time()

testA = 0
predsAr = []

# Training for 50 epochs
for e in range(50):

    epoch_start = time.time()
    print("Epoch %d start !" % (e + 1))
    # for x_batch, y_batch in zip(x_train, y_train, BATCH_SIZE):
    err = []
    preds = []
    trues = []

    # batch sizes for crimes and anomaly and prediction
    x_batch1 =[]
    x_batch2 = []
    y_batch1 = []
    
    # Recording error, prediction, truth values(for F1-scores)
    for i in range(len(x_train)-80):
        i+=80
        x_batch = x_train[i:min(len(x_train)-1,timeSize+(i))]
        x_anomaly = x_train2[i:min(len(x_train)-1,timeSize+(i))]
        if len(x_batch) < timeSize:
          continue
        x_batch = x_batch
        x_anomaly = x_anomaly
        y_batch = x_train[min(len(x_train)-1,timeSize+(i))].T
        x_batch1.append(x_batch)
        x_batch2.append(x_anomaly)
        y_batch1.append(y_batch)
        if (i+1)% BATCH_SIZE >0:
          continue
        # print(np.array(x_batch1).shape)
        fd = {batch_x: x_batch1,anomaly_x:x_batch2, batch_y: y_batch1, keep_prob: KEEP_PROB}
        # print(y_batch)
        l, _, oht = sess.run([loss, optimizer, one_hot_prediction], feed_dict=fd)
        for j in range(BATCH_SIZE):
          # print(oht.shape)
          preds.extend(np.array(oht[j]).reshape(-1,4))
          trues.extend(np.array(y_batch1[j]).reshape(-1,4))
        x_batch1 =[]
        y_batch1 = []
        x_batch2 = []

        # sess.run(optimizer,feed_dict=fd)
        err.append(l)
    # print(sess.run(loss))
    epoch_finish = time.time()
    # print(preds)
    preds = np.array(preds)
    trues = np.array(trues)
    # f1 = f1_score(y_true=y_batch, y_pred=oht, average='weighted')
    f1 = f1_score(y_true=np.where(trues>0,1,0), y_pred=np.where(preds>0,1,0), average='micro')
    f2 = f1_score(y_true=np.where(trues>0,1,0), y_pred=np.where(preds>0,1,0), average='macro')
    tr.append([f1,f2])
    # print(f1)
    print("TRain :: ",np.mean(err)," : micro ",f1," : macro",f2," : ",epoch_finish-epoch_start)
    # print(classification_report(y_true=trues,y_pred=preds,target_names=target_names))

    # Predictions on test data and storing info for visualization
    if True:
      preds = []
      trues = []
      x_batch1 =[]
      y_batch1 = []
      x_batch2 = []
      err = []
      for i in range(len(x_test)):
          # i+=100
          x_batch = x_test[i:min(len(x_test)-1,timeSize+(i))]
          x_anomaly = x_test2[i:min(len(x_test)-1,timeSize+(i))]
          if len(x_batch) < timeSize:
            continue
          x_batch = x_batch
          x_anomaly = x_anomaly
          y_batch = x_test[min(len(x_test)-1,timeSize+(i))].T
          x_batch1.append(x_batch)
          x_batch2.append(x_anomaly)
          y_batch1.append(y_batch)
          if (i+1)% BATCH_SIZE >0:
            continue
          fd = {batch_x: x_batch1,anomaly_x:x_batch2, batch_y: y_batch1, keep_prob: KEEP_PROB}
          l, acc,oht,weightSupport = sess.run([loss, accuracy,one_hot_prediction,weight_soft], feed_dict=fd)
          err.append(l)
          # sess.run(optimizer,feed_dict=fd)
          for j in range(BATCH_SIZE):
            # print(oht.shape)
            preds.extend(np.array(oht[j]).reshape(-1,4))
            trues.extend(np.array(y_batch1[j]).reshape(-1,4))

          x_batch1 =[]
          y_batch1 = []
          x_batch2 = []

      # print(preds)
      preds = np.array(preds)
      trues = np.array(trues)
      # f1 = f1_score(y_true=y_batch, y_pred=oht, average='weighted')
      f1 = f1_score(y_true=np.where(trues>0,1,0), y_pred=np.where(preds>0,1,0), average='micro')
      f2 = f1_score(y_true=np.where(trues>0,1,0), y_pred=np.where(preds>0,1,0), average='macro')
      if testA < f1:
        testA=f1
        save_path = saver.save(sess, "./modelM/model"+str(f1)[:5]+".ckpt")
        # print(classification_report(y_true=trues,y_pred=preds,target_names=target_names))
        predsAr.append(preds)
      ts.append([f1,f2])
      # print(f1)
      print(np.mean(err)," : micro ",f1," : macro",f2," : ")
      print(weightSupport)
      # print(classification_report(y_true=trues,y_pred=preds,target_names=target_names))

# Commented out IPython magic to ensure Python compatibility.
# %matplotlib notebook
import matplotlib.pyplot as plt

# This part of code is to visualize the decay in model performance as we try to predict crimes for an extended period of time, using bootstrapping

preds = []
trues = []
x_batch1 =[]
y_batch1 = []
x_batch2 = []
err = []
pp = []
x_test3 = np.array(x_test)
sub=0
for i in range(len(x_test)):
    # i+=100
    i-=sub
    x_batch = x_test3[i:min(len(x_test)-1,timeSize+(i))]
    x_anomaly = x_test2[i:min(len(x_test)-1,timeSize+(i))]
    if len(x_batch) < timeSize:
      continue
    x_batch = x_batch
    x_anomaly = x_anomaly
    y_batch = x_test[min(len(x_test)-1,timeSize+(i))].T
    x_batch1.append(x_batch)
    x_batch2.append(x_anomaly)
    y_batch1.append(y_batch)
    if (i+1)% BATCH_SIZE >0:
      continue
      sub=3
    fd = {batch_x: x_batch1,anomaly_x:x_batch2, batch_y: y_batch1, keep_prob: KEEP_PROB}
    l, acc,oht,weightSupport = sess.run([loss, accuracy,one_hot_prediction,weight_soft], feed_dict=fd)
    err.append(l)
    # sess.run(optimizer,feed_dict=fd)
    for j in range(1):
      # print(oht.shape)
      preds.extend(np.array(oht[j]).reshape(-1,4))
      trues.extend(np.array(y_batch1[j]).reshape(-1,4))
    f1 = f1_score(y_true=np.where(np.array(trues)>0,1,0), y_pred=np.where(np.array(preds)>0,1,0), average='micro')
    f2 = f1_score(y_true=np.where(np.array(trues)>0,1,0), y_pred=np.where(np.array(preds)>0,1,0), average='macro')
    print(f1," : ",f2)
    pp.append([f1,f2])

    x_batch1 =[]
    y_batch1 = []
    x_batch2 = []
    # x_test3[min(len(x_test)-1,timeSize+(i))]=np.array(oht[3]).T
    # x_test3[min(len(x_test)-1,timeSize+(i-1))]=np.array(oht[2]).T
    # x_test3[min(len(x_test)-1,timeSize+(i-2))]=np.array(oht[1]).T
    x_test3[min(len(x_test)-1,timeSize+(i-3))]=np.array(oht[0]).T
# print(preds)
preds = np.array(preds)
trues = np.array(trues)
# f1 = f1_score(y_true=y_batch, y_pred=oht, average='weighted')
f1 = f1_score(y_true=np.where(trues>0,1,0), y_pred=np.where(preds>0,1,0), average='micro')
f2 = f1_score(y_true=np.where(trues>0,1,0), y_pred=np.where(preds>0,1,0), average='macro')
# if testA < f1:
  # testA=f1
  # save_path = saver.save(sess, "./modelM/model"+str(f1)[:5]+".ckpt")
  # print(classification_report(y_true=trues,y_pred=preds,target_names=target_names))
  # predsAr.append(preds)
ts.append([f1,f2])
# print(f1)
print(np.mean(err)," : micro ",f1," : macro",f2," : ")
print(weightSupport)

# Commented out IPython magic to ensure Python compatibility.
# Plotting the above data

# %matplotlib inline
plt.plot(np.array(pp).T[0].T,label="testProg_micro")
plt.plot(np.array(pp).T[1].T,label="testProg_macro")
# plt.plot(np.array(ts).T[0].T,label="test_micro")
# plt.plot(np.array(ts).T[1].T,label="test_macro")
# plt.plot(ts)
plt.title('F1 fall progressive prediction')
plt.legend()
plt.show()

# Statistical significance

from scipy.stats import ttest_ind,ttest_rel,ks_2samp
ttest_ind(predsAr[6].reshape(-1), predsAr[7].reshape(-1))

# Seperating the model predictions to change the dimensions to (4 * days X 77) from (77 * days X 4)

np.array(predsAr[8])
a = []
b = []
i =0
ar = []
br= []
for x,y in zip(predsAr[8],trues):
  a.append(x)
  b.append(y)
  i+=1
  if i%77==0:
    ar.extend(list(np.array(a).T))
    br.extend(list(np.array(b).T))
    a = []
    b = []

br = np.array(br)
ar = np.array(ar)

print(classification_report(y_true=br,y_pred=ar))

ks_2samp(predsAr[6].reshape(-1), predsAr[8].reshape(-1))
# Statisticall significance test

# Classification scores based on crime categories 

target_names = ['robery','burgalry','felony','grand']
print(classification_report(y_true=trues,y_pred=predsAr[8],target_names=target_names))

# Plotting heatmap from crime vs locality, after reshaping for better representation

fig, ax = plt.subplots()
fig2, ax2 = plt.subplots()
fig3, ax3 = plt.subplots()

min_val, max_val = 0, 15

intersection_matrix =  predsAr[8][-77*3:].reshape((11*3,14*2)) #np.random.randint(0, 10, size=(max_val, max_val))
intersection_matrix2 = trues[-77*3:].reshape((11*3,14*2))
ax.matshow(intersection_matrix, cmap=plt.cm.Blues)
ax2.matshow(intersection_matrix2,  cmap=plt.cm.Greens)

results = [[intersection_matrix2[i][j] + intersection_matrix[i][j]  for j in range
(len(intersection_matrix2[0]))] for i in range(len(intersection_matrix2))]

ax3.matshow(results,  cmap=plt.cm.Greens)
# ax3.matshow(intersection_matrix,  cmap=plt.cm.Greens)
# for i in range(14*2):
#     for j in range(33):
#         c = intersection_matrix[j,i]
#         ax.text(i, j, str(c), va='center', ha='center')


# for i in range(14*2):
#     for j in range(33):
#         c = intersection_matrix2[j,i]
#         ax2.text(i, j, str(c), va='center', ha='center')

# Heatmaps

fig, ax = plt.subplots()
fig2, ax2 = plt.subplots()
fig3, ax3 = plt.subplots()

min_val, max_val = 0, 15

intersection_matrix =  predsAr[8][-77*2:].reshape((11*2,14*2)) #np.random.randint(0, 10, size=(max_val, max_val))
intersection_matrix2 = trues[-77*2:].reshape((11*2,14*2))
ax.matshow(intersection_matrix, cmap=plt.cm.Blues)
ax2.matshow(intersection_matrix2,  cmap=plt.cm.Greens)

results = [[intersection_matrix2[i][j] + intersection_matrix[i][j]  for j in range
(len(intersection_matrix2[0]))] for i in range(len(intersection_matrix2))]

ax3.matshow(results,  cmap=plt.cm.Greens)
# ax3.matshow(intersection_matrix,  cmap=plt.cm.Greens)
for i in range(14*2):
    for j in range(33):
        c = intersection_matrix[j,i]
        ax.text(i, j, str(c), va='center', ha='center')


for i in range(14*2):
    for j in range(33):
        c = intersection_matrix2[j,i]
        ax2.text(i, j, str(c), va='center', ha='center')