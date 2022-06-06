/*
This code is property of Samana Group LLC. You need permission from Samana Group
to use this code.

To build this code, wmic must be compiled first.
*/

#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include "structmember.h"
#include "etcd.h"
#include "client.h"
#include "exceptions.h"

#define ETCD_VERSION "1654542407"
#define PYMODULE "etcd"
#define PYOPEN_DOC "Creates an object that communicates with an ETCD server.\n\
\n\
"

#define PYVERSION_DOC "Version."

#define PYMODULE_DOC "This module provides various functions to communicate with an etcd server.\n\
\n\
"

#define PYTHON_FUNCDEF(funcname, description) \
    {                                         \
        #funcname,                            \
        etcd_ ## funcname, METH_VARARGS,     \
        description                          \
    }


static PyObject *
etcd_version(PyObject *self, PyObject *args)
{
    return PyUnicode_FromString(ETCD_VERSION);
}

static PyMethodDef PyWMIMethods[] = {
    PYTHON_FUNCDEF(version, PYVERSION_DOC),
    {NULL, NULL, 0, NULL}        /* Sentinel */
};

static struct PyModuleDef etcdmodule = {
    PyModuleDef_HEAD_INIT,
    PYMODULE,   /* name of module */
    PYMODULE_DOC,     /* module documentation, may be NULL */
    -1,       /* size of per-interpreter state of the module,
                 or -1 if the module keeps state in global variables. */
    PyWMIMethods
};


PyMODINIT_FUNC
PyInit_etcd(void)
{
    PyObject *m;

    m = PyModule_Create(&etcdmodule);
    if (m == NULL)
        return NULL;

    if(Client_InitModule(m)) {
        Py_DECREF(m);
    }
    if(EtcdException_InitModule(m)) {
        Py_DECREF(m);
    }
    if(EtcdResult_InitModule(m)) {
        Py_DECREF(m);
    }
    return m;
}

int main(int argc, char *argv[])
{

    wchar_t *program = Py_DecodeLocale(argv[0], NULL);
    if (program == NULL) {
        fprintf(stderr, "Fatal error: cannot decode argv[0]\n");
        exit(1);
    }

    /* Add a built-in module, before Py_Initialize */
    if (PyImport_AppendInittab(PYMODULE, PyInit_etcd) == -1) {
        fprintf(stderr, "Error: could not extend in-built modules table\n");
        exit(1);
    }

    /* Pass argv[0] to the Python interpreter */
    Py_SetProgramName(program);

    /* Initialize the Python interpreter.  Required.
       If this step fails, it will be a fatal error. */
    Py_Initialize();

    /* Optionally import the module; alternatively,
       import can be deferred until the embedded script
       imports it. */
    PyObject *pmodule = PyImport_ImportModule(PYMODULE);
    if (!pmodule) {
        PyErr_Print();
        fprintf(stderr, "Error: could not import module '" PYMODULE "'\n");
    }

    PyMem_RawFree(program);

    return 0;
}