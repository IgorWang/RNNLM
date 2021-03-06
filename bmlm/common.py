# -*- coding: utf-8 -*-
# Project : LM4paper
# Created by igor on 2016/11/29

import os
import time
import numpy as np

import tensorflow as tf


def assign_to_gpu(gpu=0, ps_dev="/device:CPU:0"):
    def _assign(op):
        node_def = op if isinstance(op, tf.NodeDef) else op.node_def
        if node_def.op == "Variable":
            return ps_dev
        else:
            return "/gpu:%d" % gpu

    return _assign


def find_trainable_variables(key):
    return tf.get_collection(tf.GraphKeys.TRAINABLE_VARIABLES,
                             ".*{}.*".format(key))


def load_from_checkpoint(saver, logdir):
    sess = tf.get_default_session()
    ckpt = tf.train.get_checkpoint_state(logdir)
    if ckpt and ckpt.model_checkpoint_path:
        if os.path.isabs(ckpt.model_checkpoint_path):
            saver.restore(sess, ckpt.model_checkpoint_path)
        else:
            saver.restore(sess, os.path.join(logdir, ckpt.model_checkpoint_path))
        return True
    return False


class CheckpointLoader(object):
    def __init__(self, saver, global_step, logdir):
        self.saver = saver
        self.global_step_tensor = global_step
        self.logdir = logdir
        self.last_global_step = 0

    def load_checkpoint(self):
        while True:
            if load_from_checkpoint(self.saver, self.logdir):
                global_step = int(self.global_step_tensor.eval())
                if global_step <= self.last_global_step:
                    print("Waiting for a new checkpoint")
                    time.sleep(60)
                    continue
                print("Successfully loaded model at step=%s." % global_step)
            else:
                print("No checkpoint file found. Waiting...")
                time.sleep(60)
                continue
            self.last_global_step = global_step
            return True


def average_grads(tower_grads):
    def average_dense(grad_and_vars):
        if len(grad_and_vars) == 1:
            return grad_and_vars[0][0]

        grad = grad_and_vars[0][0]
        for g, _ in grad_and_vars[1:]:
            grad += g

        return grad / len(grad_and_vars)

    def average_sparse(grad_and_vars):
        if len(grad_and_vars) == 1:
            return grad_and_vars[0][0]

        indices = []
        values = []

        for g, _ in grad_and_vars:
            indices += [g.indices]
            values += [g.values]
        indices = tf.concat(0, indices)
        values = tf.concat(0, values)

        return tf.IndexedSlices(values, indices,
                                grad_and_vars[0][0].dense_shape)

    aver_grads = []
    for grad_and_vars in zip(*tower_grads):
        if grad_and_vars[0][0] is None:
            grad = None
        elif isinstance(grad_and_vars[0][0], tf.IndexedSlices):
            grad = average_sparse(grad_and_vars)
        else:
            grad = average_dense(grad_and_vars)
        v = grad_and_vars[0][1]
        grad_and_vars = (grad, v)
        aver_grads.append(grad_and_vars)
    return aver_grads

