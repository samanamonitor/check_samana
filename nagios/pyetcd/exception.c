#include <Python.h>
#include "structmember.h"
#include <jansson.h>
#include "etcd.h"

PyObject *EtcdException;
PyObject *EtcdValueError;
PyObject *EtcdCompareFailed;
PyObject *EtcdClusterIdChangedm;
PyObject *EtcdKeyError;
PyObject *EtcdKeyNotFound;
PyObject *EtcdNotFile;
PyObject *EtcdNotDir;
PyObject *EtcdAlreadyExist;
PyObject *EtcdEventIndexCleared;
PyObject *EtcdConnectionFailed;
PyObject *EtcdWatcherCleared;
PyObject *EtcdLeaderElectionInProgress;
PyObject *EtcdRootReadOnly;
PyObject *EtcdDirNotEmpty;
PyObject *EtcdLockExpired;

typedef struct {
    PyObject_HEAD
    int errorCode;
    PyObject *message;
    PyObject *cause;
    int index;
} EtcdErrorObject;


PRIVATE
PyObject *Error_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
    EtcdErrorObject *self;
    self = (EtcdErrorObject *) type->tp_alloc(type, 0);
    if (self == NULL) goto exit;

    self->message = PyUnicode_FromString("");
    if (self->message == NULL) {
        Py_DECREF(self);
        return NULL;
    }
    self->cause = PyUnicode_FromString("");
    if (self->cause == NULL) {
        Py_DECREF(self);
        return NULL;
    }
    self->errorCode = 0;
    self->index = 0;
    exit:
    return (PyObject *) self;
}

PRIVATE 
int Error_init(EtcdErrorObject *self, PyObject *args, PyObject *kwds)
{
    static char *kwlist[] = {"json", NULL};
    int error = 0;
    PyObject *message = NULL, *cause = NULL, *py_json = NULL;
    int errorCode, index;

    if (!PyArg_ParseTupleAndKeywords(args, kwds, "|O", kwlist, &py_json))
        return -1;

    char *json_str = PyUnicode_AsUTF8(py_json);
    if(json_str == NULL) {
        PyErr_Format(EtcdException, "Invalid Init data %S", py_json);
        goto exit;
    }
    json_error_t error_json;
    json_t *root = NULL;
    root = json_loads(json_str, 0, &error_json);
    if(!root) {
        PyErr_Format(EtcdException, "JSON error: on line %d: %s\n%s", error_json.line, error_json.text, json_str);
        error = -1;
        goto exit;
    }
    if(!json_is_object(root)) {
        PyErr_Format(EtcdException, "JSON error: root is not an object. %s\n", json_str);
        error = -1;
        goto exit;
    }
    JSON_OBJECT_GET_STRING(root, message);
    REPLACE_MEMBER(self->message, message);

    JSON_OBJECT_GET_STRING(root, cause);
    REPLACE_MEMBER(self->cause, cause);

    JSON_OBJECT_GET_INTEGER(root, errorCode);
    self->errorCode = errorCode;

    JSON_OBJECT_GET_INTEGER(root, index);
    self->index = index;

    exit:
    if(root) json_decref(root);
    return error;
}

PRIVATE
void Error_dealloc(EtcdErrorObject *self)
{
    Py_XDECREF(self->message);
    Py_XDECREF(self->cause);
    Py_TYPE(self)->tp_free((PyObject *) self);
}

PRIVATE 
PyObject *Error_str(PyObject *s)
{
    EtcdErrorObject *self = (EtcdErrorObject *) s;
    if (self->message == NULL) {
        PyErr_SetString(PyExc_AttributeError, "message");
        return NULL;
    }
    if (self->cause == NULL) {
        PyErr_SetString(PyExc_AttributeError, "cause");
        return NULL;
    }
    return PyUnicode_FromFormat("Error Code: %d, Message: \"%S\", Cause: \"%S\"", self->errorCode,
        self->message, self->cause);
}

PRIVATE 
PyMemberDef Error_members[] = {
    {"errorCode", T_INT, offsetof(EtcdErrorObject, errorCode), 0,
     "Etcd Error code - Expects Int"},
    {"message", T_OBJECT_EX, offsetof(EtcdErrorObject, message), 0,
     "Etcd Error message - Expects String"},
    {"cause", T_OBJECT_EX, offsetof(EtcdErrorObject, cause), 0,
     "Etcd Error cause - Expects String"},
    {"index", T_INT, offsetof(EtcdErrorObject, index), 0,
     "Etcd Message index - Expects Int"},
    {NULL}  /* Sentinel */
};

PUBLIC
PyTypeObject EtcdErrorType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "etcd.EtcError",
    .tp_doc = PyDoc_STR("Etcd Error objects"),
    .tp_basicsize = sizeof(EtcdErrorObject),
    .tp_itemsize = 0,
    .tp_flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,
    .tp_new = Error_new,
    .tp_init = (initproc) Error_init,
    .tp_dealloc = (destructor) Error_dealloc,
    .tp_members = Error_members,
    .tp_str = Error_str,
};

PUBLIC
PyObject *EtcdError_FromString(const char *s)
{
    PyObject *err_str = PyUnicode_FromString(s);
    PyObject *args = PyTuple_New(1);
    if (args == NULL) {
        PyErr_SetString(PyExc_AttributeError, "Unable to create Tuple");
        Py_XDECREF(err_str);
        return NULL;
    }
    if(PyTuple_SetItem(args, 0, err_str)) {
        return NULL;
    }
    PyObject *err = Error_new(&EtcdErrorType, NULL, NULL);
    if(err == NULL) {
        PyErr_SetString(PyExc_AttributeError, "Unable to create Object");
        goto exit;
    }
    Error_init((EtcdErrorObject*)err, args, NULL);
    exit:
    Py_XDECREF(args);
    return err;
}

PUBLIC
int EtcdException_InitModule(PyObject *m)
{
    if (PyType_Ready(&EtcdErrorType) < 0)
        return -1;
    Py_INCREF(&EtcdErrorType);
    if (PyModule_AddObject(m, "EtcdError", (PyObject *) &EtcdErrorType) < 0) {
        Py_DECREF(&EtcdErrorType);
        return -1;
    }
    DEF_EXCEPTION(m, EtcdException, NULL);
    DEF_EXCEPTION(m, EtcdValueError, EtcdException);
    DEF_EXCEPTION(m, EtcdCompareFailed, EtcdValueError);
    DEF_EXCEPTION(m, EtcdClusterIdChangedm, EtcdException);
    DEF_EXCEPTION(m, EtcdKeyError, EtcdException);
    DEF_EXCEPTION(m, EtcdKeyNotFound, EtcdKeyError);
    DEF_EXCEPTION(m, EtcdNotFile, EtcdKeyError);
    DEF_EXCEPTION(m, EtcdNotDir, EtcdKeyError);
    DEF_EXCEPTION(m, EtcdAlreadyExist, EtcdKeyError);
    DEF_EXCEPTION(m, EtcdEventIndexCleared, EtcdException);
    DEF_EXCEPTION(m, EtcdConnectionFailed, EtcdException);
    DEF_EXCEPTION(m, EtcdWatcherCleared, EtcdException);
    DEF_EXCEPTION(m, EtcdLeaderElectionInProgress, EtcdException);
    DEF_EXCEPTION(m, EtcdRootReadOnly, EtcdKeyError);
    DEF_EXCEPTION(m, EtcdDirNotEmpty, EtcdValueError);
    DEF_EXCEPTION(m, EtcdLockExpired, EtcdException);
    return 0;
}