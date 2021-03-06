
#-*- coding:utf-8 -*-

import numpy as np
import sys

from pandas import Series
from scipy.spatial.distance import cdist
from sklearn.metrics import precision_recall_curve, average_precision_score
from sklearn.metrics import roc_curve, roc_auc_score, f1_score


def evaluate(model, X_test, Y_test, threshold, first_k=0):

    Y_hats = np.zeros(Y_test.shape)
    for i in xrange(len(X_test)):
        Y_hats[i,:] = model.predict_proba(X_test[i])[0]


    if first_k>0.0:
        yh = Y_hats[:,:k]
        yt = Y_test[:,:k]

    else:
        yh = Y_hats
        yt = Y_test

    print "calculating F1"
    f1, p, r = F1(yh, yt, threshold)

    print "calculating AUC"
    (ROC, AUC, throwaway) = ROC_AUC(yh,yt)




    return (AUC,p, r, f1)


def F1(Y_hats, Y_test, threshold):
    YH = Y_hats > threshold

    tp =(YH > .5) & (Y_test > 0)
    p = tp.sum()*1.0 / YH.sum()
    #print "tpsum: %s, YHsum: %s" % (tp.sum(), YH.sum())
    r = tp.sum()*1.0 / Y_test.sum()
    return  ((2 * p * r) / (p + r)), p, r

def ROC_AUC(Y_hats, Y_test):

    #print "calculating number of true positives"
    total_positives = Y_test.sum()*1.0
    total_negatives = len(Y_test.flatten())*1.0 - total_positives

    #print "sorting predictions by score"
    sorted_pred = sorted(zip(Y_hats.flatten(), Y_test.flatten()), key=lambda x: -1*x[0])

    tp = 0.0
    fp = 0.0

    ROC = []

    #print("passing through sorted predictions")
    for yh, gt in sorted_pred:
        #print "yh: %s, gt: %s" % (yh, gt)
        if gt == 1.0:
            tp += 1.0
        else:
            fp += 1.0

        ROC += [((fp/total_negatives), (tp/total_positives))]

    #calculate area under the curve
    l = len(ROC)
    AUC = 0.0
    for x, y in ROC:
        AUC += y * (1.0/l)

    thresholds = zip(*sorted_pred)[0]
    return ROC, AUC, list(thresholds)

def PRC_AUC(Y_hats, Y_test):
    p,r,thresholds = precision_recall_curve(Y_test.flatten(), Y_hats.flatten())
    thresholds = np.hstack([thresholds, thresholds[-1]])
    prc = np.vstack([r,p]).T
    auc = average_precision_score(Y_test.flatten(), Y_hats.flatten(), average='micro')
    return prc, auc, thresholds

def f1_curve(Y_hats, Y_test):
    p,r,thresholds = precision_recall_curve(Y_test.flatten(), Y_hats.flatten())
    thresholds = np.hstack([thresholds, thresholds[-1]])
    f1 = (2 * p * r) / (p + r)
    return f1, thresholds

def optimize_threshold_with_roc(roc, thresholds, criterion='dist'):
    if roc.shape[1] > roc.shape[0]:
        roc = roc.T
    assert(roc.shape[0] == thresholds.shape[0])
    if criterion == 'margin':
        scores = roc[:,1]-roc[:,0]
    else:
        scores = -cdist(np.array([[0,1]]), roc)
    ti = np.nanargmax(scores)
    return thresholds[ti], ti

def optimize_threshold_with_prc(prc, thresholds, criterion='min'):
    prc[np.isnan(prc)] = 0
    if prc.shape[1] > prc.shape[0]:
        prc = prc.T
    assert(prc.shape[0] == thresholds.shape[0])
    if criterion == 'sum':
        scores = prc.sum(axis=1)
    elif criterion.startswith('dist'):
        scores = -cdist(np.array([[1,1]]), prc)
    else:
        scores = prc.min(axis=1)
    ti = np.nanargmax(scores)
    return thresholds[ti], ti

mp = np.finfo(float).eps

def optimize_threshold_with_f1(f1c, thresholds, criterion='max'):
    #f1c[np.isnan(f1c)] = 0
    if criterion == 'max':
        ti = np.nanargmax(f1c)
    else:
        ti = np.nanargmin(np.abs(thresholds-0.5*f1c))
        #assert(np.all(thresholds>=0))
        #idx = (thresholds>=f1c*0.5-mp) & (thresholds<=f1c*0.5+mp)
        #assert(np.any(idx))
        #ti = np.where(idx)[0][f1c[idx].argmax()]
    return thresholds[ti], ti

def random_split(n, test_frac=0.1):
    all_idx = np.arange(n)
    test_idx = all_idx[np.random.choice(n, int(np.ceil(test_frac*n)), replace=False)]
    train_idx = np.setdiff1d(all_idx, test_idx)
    assert(np.all(np.sort(np.hstack([train_idx, test_idx])) == all_idx))
    return train_idx, test_idx

def generate_one_split(Y, test_frac=0.1, valid_frac=0.1, minpos=10, verbose=0):
    split = None

    if verbose > 0:
        sys.stdout.write('Generating {0} test split'.format(test_frac))
        sys.stdout.flush()
    while split is None:
        if verbose > 0:
            sys.stdout.write('.')
            sys.stdout.flush()
        not_test_idx, test_idx = random_split(Y.shape[0], test_frac=test_frac)
        assert(np.all(np.sort(np.hstack([not_test_idx,test_idx])) == np.arange(Y.shape[0])))
        if np.all(Y[not_test_idx,:].sum(axis=0)>=2*minpos) and np.all(Y[test_idx,:].sum(axis=0)>=minpos):
            if verbose > 0:
                sys.stdout.write('Generating {0}/{1} train/test splits'.format(1-(test_frac+valid_frac), valid_frac))
                sys.stdout.flush()
            while split is None:
                if verbose > 0:
                    sys.stdout.write('.')
                    sys.stdout.flush()
                train_idx, valid_idx = random_split(Y[not_test_idx].shape[0], test_frac=valid_frac/(1-test_frac))
                assert(np.all(np.sort(np.hstack((train_idx, valid_idx))) == np.arange(Y[not_test_idx].shape[0])))
                if np.all(Y[not_test_idx,:][train_idx,:].sum(axis=0)>=minpos) and np.all(Y[not_test_idx,:][valid_idx,:].sum(axis=0)>=minpos):
                    split = ( np.sort(not_test_idx[train_idx]), np.sort(not_test_idx[valid_idx]), np.sort(test_idx) )
                    sys.stdout.write('DONE!\n')
                    break

    return split

def generate_splits(Y, num_splits=10, test_frac=0.1, valid_frac=0.1, minpos=10, verbose=0):
    return [ generate_one_split(Y, test_frac=test_frac, valid_frac=valid_frac, minpos=minpos, verbose=verbose) for i in range(num_splits) ]
