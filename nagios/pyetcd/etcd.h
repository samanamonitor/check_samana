#ifndef __ETCD_H__
#define __ETCD_H__

#include <jansson.h>

#define VERBOSE_OFF 0L
#define VERBOSE_ON 1L
#define VERBOSE VERBOSE_OFF
#define BUFFER_START_LEN 50
#define FREE(x) if(x) free(x);
#define PUBLIC
#define PRIVATE static

#define INIT_ERROR_GOTO(t) if(t) goto error

#define DEF_EXCEPTION(m,n,b) \
    n = PyErr_NewException(#n ".error", b, NULL);\
    if(n == NULL) {\
        return -1;\
    }\
    if(PyModule_AddObject(m, #n, (PyObject *)n) < 0) {\
        Py_XDECREF(&n);\
        return -1;\
    }

#define REPLACE_MEMBER(m, v) {\
    PyObject *__v = v;\
    if(__v) {\
        PyObject *tmp = m;\
        m = __v;\
        Py_XDECREF(tmp);\
    }\
}

#define JSON_OBJECT_GET_STRING(root, v) { \
    json_t *__temp = json_object_get(root, #v); \
    if(!json_is_string(__temp)) { \
        PyErr_Format(EtcdException, "JSON error: '" #v "' is not defined. %s\n", json_str); \
        json_decref(__temp); \
        error = -1; \
        goto exit; \
    } \
    v = PyUnicode_FromString(json_string_value(__temp)); \
    json_decref(__temp); \
}

#define JSON_OBJECT_GET_INTEGER(root, v) { \
    json_t *__temp = json_object_get(root, #v); \
    if(!json_is_integer(__temp)) { \
        PyErr_Format(EtcdException, "JSON error: '" #v "' is not defined. %s\n", json_str); \
        json_decref(__temp); \
        error = -1; \
        goto exit; \
    } \
    v = json_integer_value(__temp); \
    json_decref(__temp); \
}

int EtcdResult_InitModule(PyObject *m);
PyObject *EtcdResult_FromString(const char *s);
PyObject *EtcdResult_FromJSON(json_t *root);
PyObject *EtcdResult_FromDict(PyObject *dict);
#endif