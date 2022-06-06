#ifndef __EXCEPTIONS_H__
#define __EXCEPTIONS_H__
extern PyObject *EtcdException;
extern PyObject *EtcdValueError;
extern PyObject *EtcdCompareFailed;
extern PyObject *EtcdClusterIdChangedm;
extern PyObject *EtcdKeyError;
extern PyObject *EtcdKeyNotFound;
extern PyObject *EtcdNotFile;
extern PyObject *EtcdNotDir;
extern PyObject *EtcdAlreadyExist;
extern PyObject *EtcdEventIndexCleared;
extern PyObject *EtcdConnectionFailed;
extern PyObject *EtcdWatcherCleared;
extern PyObject *EtcdLeaderElectionInProgress;
extern PyObject *EtcdRootReadOnly;
extern PyObject *EtcdDirNotEmpty;
extern PyObject *EtcdLockExpired;
PyObject *EtcdError_FromString(const char *s);
int EtcdException_InitModule(PyObject *m);
#endif