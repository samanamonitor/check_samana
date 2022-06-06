#include <Python.h>
#include "structmember.h"
#include <jansson.h>
#include "etcd.h"
#include "exceptions.h"

PyObject *EtcdResult;

typedef struct {
    PyObject_HEAD
    PyObject *raw;
    PyObject *key;
    PyObject *value;
    PyObject *nodes;
    PyObject *expiration;
    PyObject *ttl;
    PyObject *modifiedIndex;
    PyObject *createdIndex;
    int newKey;
    PyObject *dir;
} ResultObject;

PRIVATE
PyObject *PyObject_FromJSON(json_t *j)
{
    if(json_is_object(j)) {
        const char *key;
        json_t *value;
        PyObject *out = PyDict_New();
        json_object_foreach(j, key, value) {
            PyObject *v=PyObject_FromJSON(value);
            if(v == NULL) {
                Py_XDECREF(out);
                return NULL;
            }
            PyDict_SetItemString(out, key, v);
            Py_XDECREF(v);
        }
        return out;
    } else if(json_is_array(j)) {
        size_t index;
        json_t *value;
        PyObject *out = PyList_New(json_array_size(j));

        json_array_foreach(j, index, value) {
            PyObject *i = PyObject_FromJSON(value);
            if(i == NULL) {
                Py_XDECREF(out);
                return NULL;
            }
            PyList_SetItem(out, index, i);
        }
        return out;
    } else if(json_is_string(j)) {
        return PyUnicode_FromString(json_string_value(j));
    } else if(json_is_integer(j)) {
        return PyLong_FromLong(json_integer_value(j));
    } else if(json_is_real(j)) {
        return PyFloat_FromDouble(json_real_value(j));
    } else if(json_is_true(j)) {
        Py_RETURN_TRUE;
    } else if(json_is_false(j)) {
        Py_RETURN_FALSE;
    } else if(json_is_null(j)) {
        Py_RETURN_NONE;
    }
    PyErr_SetString(EtcdException, "Invalid JSON data");
    return NULL;
}

PRIVATE
PyObject *Result_FromDict(ResultObject *self, PyObject *args, PyObject *kwds)
{
    static char *kwlist[] = {"dict", NULL};

    PyObject *dict = NULL;
    if (!PyArg_ParseTupleAndKeywords(args, kwds, "|O", kwlist, &dict))
        return NULL;

    if(PyObject_IsInstance(dict, (PyObject*) &PyDict_Type) < 1) {
        PyErr_SetString(PyExc_AttributeError, "A Dictionary is required");
        return NULL;
    }

    REPLACE_MEMBER(self->raw, Py_BuildValue("{s:O,s:s}", "dict", dict, "str", ""));

    PyObject *py_key = PyDict_GetItemString(dict, "key");
    if(py_key == NULL) {
        self->key = PyUnicode_FromString("/");
    } else {
        REPLACE_MEMBER(self->key, py_key);
        Py_XINCREF(py_key);
    }

    PyObject *py_modifiedIndex = PyDict_GetItemString(dict, "modifiedIndex");
    if(py_modifiedIndex == NULL) {
        self->modifiedIndex = PyLong_FromLong(0);
    } else {
        REPLACE_MEMBER(self->modifiedIndex, py_modifiedIndex);
        Py_XINCREF(py_modifiedIndex);
    }

    PyObject *py_createdIndex = PyDict_GetItemString(dict, "createdIndex");
    if(py_createdIndex == NULL) {
        self->createdIndex = PyLong_FromLong(0);
    } else {
        REPLACE_MEMBER(self->createdIndex, py_createdIndex);
        Py_XINCREF(py_createdIndex);
    }

    REPLACE_MEMBER(self->dir, PyDict_GetItemString(dict, "dir"));
    Py_XINCREF(self->dir);

    PyObject *py_nodes = PyDict_GetItemString(dict, "nodes");
    if(py_nodes && PyObject_IsInstance(py_nodes, (PyObject*) &PyList_Type)) {
        long nodes_len = PyList_Size(py_nodes);
        PyObject *py_nodes_list = PyList_New(nodes_len);
        for(int i=0; i< nodes_len; i++) {
            PyObject *item = PyList_GetItem(py_nodes, i);
            PyList_SetItem(py_nodes_list, i, EtcdResult_FromDict(item));
        }
        REPLACE_MEMBER(self->nodes, py_nodes_list);
    }
    /* TODO: add nodes */

    PyObject *py_value = PyDict_GetItemString(dict, "value");
    if(py_value) {
        REPLACE_MEMBER(self->value, py_value);
        Py_XINCREF(py_value);
    }

    PyObject *py_ttl = PyDict_GetItemString(dict, "ttl");
    if(py_ttl) {
        REPLACE_MEMBER(self->ttl, py_ttl);
        Py_XINCREF(py_ttl);
    }
    return (PyObject*)self;
}

PRIVATE
PyObject *Result_FromString(ResultObject *self, PyObject *args, PyObject *kwds)
{
    static char *kwlist[] = {"json_string", NULL};

    PyObject *py_json_string = NULL;
    if (!PyArg_ParseTupleAndKeywords(args, kwds, "|O", kwlist, &py_json_string))
        return NULL;

    if(PyObject_IsInstance(py_json_string, (PyObject*) &PyUnicode_Type) < 1) {
        PyErr_SetString(PyExc_AttributeError, "A String is required");
        return NULL;
    }
    REPLACE_MEMBER(self->raw, Py_BuildValue("{s:O}", "str", py_json_string));

    char *json_str = PyUnicode_AsUTF8(py_json_string);
    if(json_str == NULL) {
        PyErr_Format(EtcdException, "Invalid Init data %S", py_json_string);
        return NULL;
    }
    json_error_t error_json;
    json_t *root = json_loads(json_str, 0, &error_json);
    if(!root) {
        PyErr_Format(EtcdException, "JSON error: on line %d: %s\n%s", error_json.line, error_json.text, json_str);
        return NULL;
    }
    if(!json_is_object(root)) {
        PyErr_Format(EtcdException, "JSON error: root is not an object. %s\n", json_str);
        if(root) json_decref(root);
        return NULL;
    }
    PyObject *py_dict = PyObject_FromJSON(root);
    if(root) json_decref(root);
    if(py_dict == NULL) return NULL;
    PyDict_SetItemString(self->raw, "dict", py_dict);
    kwds = Py_BuildValue("{s:O}", "dict", py_dict);
    args = Py_BuildValue("()");
    Result_FromDict(self, args, kwds);
    Py_XDECREF(kwds);
    Py_XDECREF(args);
    Py_XDECREF(py_dict);
    return (PyObject*) self;
}

PRIVATE
PyObject *Result_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
    ResultObject *self;
    self = (ResultObject *) type->tp_alloc(type, 0);
    if(self == NULL) return NULL;

    self->raw = PyDict_New();
    INIT_ERROR_GOTO(self->raw == NULL);
    self->key = PyUnicode_FromString("");
    INIT_ERROR_GOTO(self->key == NULL);
    self->value = PyUnicode_FromString("");
    INIT_ERROR_GOTO(self->value == NULL);
    self->expiration = PyUnicode_FromString("");
    INIT_ERROR_GOTO(self->expiration == NULL);
    self->modifiedIndex = PyLong_FromLong(0);
    INIT_ERROR_GOTO(self->modifiedIndex == NULL);
    self->createdIndex = PyLong_FromLong(0);
    INIT_ERROR_GOTO(self->createdIndex == NULL);
    self->ttl = Py_None;
    Py_INCREF(Py_None);
    self->nodes = Py_None;
    Py_INCREF(Py_None);
    self->dir = Py_None;
    Py_INCREF(Py_None);
    return (PyObject *) self;

    error:
    Py_XDECREF(self->raw);
    Py_XDECREF(self->key);
    Py_XDECREF(self->value);
    Py_XDECREF(self->expiration);
    Py_XDECREF(self->modifiedIndex);
    Py_XDECREF(self->createdIndex);
    Py_XDECREF(self->ttl);
    Py_XDECREF(self->nodes);
    Py_XDECREF(self->dir);

    Py_XDECREF(self);
    return NULL;
}

PRIVATE 
int Result_init(ResultObject *self, PyObject *args, PyObject *kwds)
{
    static char *kwlist[] = {"json_string", "dict", NULL};
    int error = 0;
    PyObject *py_json_string = NULL, *py_dict = NULL;

    if (!PyArg_ParseTupleAndKeywords(args, kwds, "|OO", kwlist, &py_json_string, &py_dict))
        return -1;
    if(py_json_string == NULL && py_dict == NULL) {
        PyErr_SetString(PyExc_AttributeError, "Need to define at least 1 parameter, json_string or dict");
        return -1;
    }
    if(py_json_string && py_dict) {
        PyErr_SetString(PyExc_AttributeError, "Cannot define both parameters at the same time");
        return -1;
    }
    if (py_dict && PyObject_IsInstance(py_dict, (PyObject*) &PyDict_Type) != 1) {
        PyErr_SetString(PyExc_AttributeError, "Parameter 'dict' must be a Dictionary");
        return -1;
    }
    if (py_json_string && PyObject_IsInstance(py_json_string, (PyObject*) &PyUnicode_Type) != 1) {
        PyErr_SetString(PyExc_AttributeError, "Parameter 'json_string' must be a String");
        return -1;
    }
    if(py_json_string){
        kwds = Py_BuildValue("{s:O}", "json_string", py_json_string);
        args = Py_BuildValue("()");
        Result_FromString(self, args, kwds);
        Py_XDECREF(kwds);
        Py_XDECREF(args);
    } else {
        kwds = Py_BuildValue("{s:O}", "dict", py_dict);
        args = Py_BuildValue("()");
        Result_FromDict(self, args, kwds);
        Py_XDECREF(kwds);
        Py_XDECREF(args);
    }
    return error;
}

PRIVATE
void Result_dealloc(ResultObject *self)
{
    Py_XDECREF(self->raw);
    Py_XDECREF(self->key);
    Py_XDECREF(self->value);
    Py_XDECREF(self->expiration);
    Py_XDECREF(self->modifiedIndex);
    Py_XDECREF(self->createdIndex);
    Py_XDECREF(self->ttl);
    Py_XDECREF(self->nodes);
    Py_XDECREF(self->dir);

    Py_TYPE(self)->tp_free((PyObject *) self);
}

PRIVATE 
PyObject *Result_str(PyObject *s)
{
    ResultObject *self = (ResultObject *) s;
    if (self->raw == NULL) {
        PyErr_SetString(PyExc_AttributeError, "raw");
        return NULL;
    }
    return PyUnicode_FromFormat("raw=%S", self->raw);
}

PRIVATE 
PyMemberDef Result_members[] = {
    {"raw", T_OBJECT_EX, offsetof(ResultObject, raw), 0,
     "Etcd Result raw - Expects String"},
    {"key", T_OBJECT_EX, offsetof(ResultObject, key), 0,
     "Key - Expects String"},
    {"modifiedIndex", T_OBJECT_EX, offsetof(ResultObject, modifiedIndex), 0,
     "ModifiedIndex - Expects Int"},
    {"createdIndex", T_OBJECT_EX, offsetof(ResultObject, createdIndex), 0,
     "CreatedIndex - Expects Int"},
    {"dir", T_OBJECT_EX, offsetof(ResultObject, dir), 0,
     "Is Directory - Expects Boolean"},
    {"value", T_OBJECT_EX, offsetof(ResultObject, value), 0,
     "value - Expects string"},
    {"nodes", T_OBJECT_EX, offsetof(ResultObject, nodes), 0,
     "nodes - Expects Array"},
    {"ttl", T_OBJECT_EX, offsetof(ResultObject, ttl), 0,
     "ttl - Expects int"},     
    {NULL}  /* Sentinel */
};

PRIVATE 
PyMethodDef Result_methods[] = {
    {"FromDict", (PyCFunction) Result_FromDict, METH_VARARGS | METH_KEYWORDS,
     "Builds Result object from a dictionary.\n\
     :param dict:  Expect a Dictionary"
    },    
    {"FromString", (PyCFunction) Result_FromString, METH_VARARGS | METH_KEYWORDS,
     "Builds Result object from a string.\n\
     :param json_string:  Expect a strin"
    },    
    {NULL}  /* Sentinel */
};

PUBLIC
PyTypeObject ResultType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "etcd.Result",
    .tp_doc = PyDoc_STR("Etcd Result objects"),
    .tp_basicsize = sizeof(ResultObject),
    .tp_itemsize = 0,
    .tp_flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,
    .tp_new = Result_new,
    .tp_init = (initproc) Result_init,
    .tp_dealloc = (destructor) Result_dealloc,
    .tp_members = Result_members,
    .tp_methods = Result_methods,
    .tp_str = Result_str,
};

PUBLIC
PyObject *EtcdResult_FromDict(PyObject *dict)
{
    PyObject *raw = Result_new(&ResultType, NULL, NULL);
    if(raw == NULL) {
        PyErr_SetString(PyExc_AttributeError, "Unable to create Object");
        return NULL;
    }

    PyObject *kwds = Py_BuildValue("{s:O}", "dict", dict);
    PyObject *args = Py_BuildValue("()");
    Result_FromDict((ResultObject*)raw, args, kwds);
    Py_XDECREF(kwds);
    Py_XDECREF(args);
    return raw;
}

PUBLIC
PyObject *EtcdResult_FromString(const char *s)
{
    PyObject *args = Py_BuildValue("()");
    PyObject *kwds = Py_BuildValue("{s:s}", "json_string", s);
    PyObject *r = Result_new(&ResultType, NULL, NULL);
    Py_XDECREF(args);
    Py_XDECREF(kwds);
    if(r == NULL) {
        PyErr_SetString(PyExc_AttributeError, "Unable to create Object");
        return NULL;
    }
    Result_init((ResultObject*)r, args, kwds);

    return r;
}

PUBLIC
PyObject *EtcdResult_FromJSON(json_t *root)
{
    if(!json_is_object(root)) {
        PyErr_SetString(EtcdException, "JSON error: root is not an object.\n");
        return NULL;
    }
    PyObject *py_dict = PyObject_FromJSON(root);
    if(py_dict == NULL) return NULL;
    PyObject *r = EtcdResult_FromDict(py_dict);
    Py_XDECREF(py_dict);
    return r;
}

PUBLIC
int EtcdResult_InitModule(PyObject *m)
{
    if (PyType_Ready(&ResultType) < 0)
        return -1;
    Py_INCREF(&ResultType);
    if (PyModule_AddObject(m, "Result", (PyObject *) &ResultType) < 0) {
        Py_DECREF(&ResultType);
        return -1;
    }
    return 0;
}