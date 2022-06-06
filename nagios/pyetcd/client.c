#include <Python.h>
#include "structmember.h"
#include <curl/curl.h>
#include "exceptions.h"
#include "etcd.h"
#include <jansson.h>


struct memory {
    char *response;
    size_t size;
    size_t pos;
};

PRIVATE
size_t read_callback(char *ptr, size_t size, size_t nmemb, void *userdata)
{
    struct memory *m = (struct memory*) userdata;
    size_t max_s = size + nmemb;
    size_t sent = (m->size - m->pos > max_s ? max_s : m->size - m->pos);
    memcpy(ptr, m->response + m->pos, sent);
    ptr[sent] = '\0';
    m->pos += sent;
    return sent;
}

PRIVATE
size_t write_callback(void *data, size_t size, size_t nmemb, void *userp)
{
    size_t realsize = size * nmemb;
    struct memory *mem = (struct memory *)userp;

    char *ptr = realloc(mem->response, mem->size + realsize + 1);
    if(ptr == NULL)
        return 0;  /* out of memory! */

    mem->response = ptr;
    memcpy(&(mem->response[mem->size]), data, realsize);
    mem->size += realsize;
    mem->response[mem->size] = 0;

    return realsize;
}

typedef struct {
    PyObject_HEAD
    PyObject *host;
    int port;                 /* Default 2379 */
    PyObject *version_prefix; /* Default 'v2' */
    int read_timeout;         /* Default 60 */
    int allow_redirect;
    PyObject *protocol;       /* Default 'http' */
    PyObject *cert;
    PyObject *ca_cert;
    int allow_reconnect;
    PyObject *use_proxies;
    PyObject *expected_cluster_id;
    int per_host_pool_size;
} ClientObject;

PRIVATE
void Client_dealloc(ClientObject *self)
{
    Py_XDECREF(self->host);
    Py_XDECREF(self->protocol);
    Py_TYPE(self)->tp_free((PyObject *) self);
}

PRIVATE
PyObject *Client_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
    ClientObject *self;
    self = (ClientObject *) type->tp_alloc(type, 0);
    if (self != NULL) {
        self->host = PyUnicode_FromString("");
        if (self->host == NULL) {
            Py_DECREF(self);
            return NULL;
        }
        self->protocol = PyUnicode_FromString("");
        if (self->protocol == NULL) {
            Py_DECREF(self);
            return NULL;
        }
        self->version_prefix = PyUnicode_FromString("");
        if (self->version_prefix == NULL) {
            Py_DECREF(self);
            return NULL;
        }
        self->port = 0;
        self->read_timeout = 60;
    }
    return (PyObject *) self;
}

PRIVATE 
int Client_init(ClientObject *self, PyObject *args, PyObject *kwds)
{
    static char *kwlist[] = {"host", "port", "version_prefix", 
        "read_timeout", "allow_redirect", "protocol", "cert",
        "ca_cert", "allow_reconnect", "use_proxies", 
        "expected_cluster_id", "per_host_pool_size", NULL};
    PyObject *host = NULL, *version_prefix = NULL, *protocol = NULL,
        *cert = NULL, *ca_cert = NULL, *use_proxies = NULL,
        *expected_cluster_id = NULL;


    if (!PyArg_ParseTupleAndKeywords(args, kwds, "|OiOipOOOpOOi", kwlist,
                                     &host, &self->port, &version_prefix, 
                                     &self->read_timeout, &self->allow_redirect, &protocol,
                                     &cert, &ca_cert, &self->allow_reconnect,
                                     &use_proxies, &expected_cluster_id, 
                                     &self->per_host_pool_size))
        return -1;

    REPLACE_MEMBER(self->host, host);
    Py_INCREF(host);
    if(version_prefix) {
        REPLACE_MEMBER(self->version_prefix, version_prefix);
        Py_INCREF(version_prefix);
    } else {
        REPLACE_MEMBER(self->version_prefix, PyUnicode_FromString("v2"));
    }
    if(protocol) {
        REPLACE_MEMBER(self->protocol, protocol);
        Py_INCREF(protocol);
    } else {
        REPLACE_MEMBER(self->protocol, PyUnicode_FromString("http"));
    }
    return 0;
}

PRIVATE 
PyObject *
Client_url(ClientObject *self, PyObject *Py_UNUSED(ignored))
{
    if (self->host == NULL) {
        PyErr_SetString(PyExc_AttributeError, "host");
        return NULL;
    }
    if (self->version_prefix == NULL) {
        PyErr_SetString(PyExc_AttributeError, "version_prefix");
        return NULL;
    }
    if (self->protocol == NULL) {
        PyErr_SetString(PyExc_AttributeError, "protocol");
        return NULL;
    }
    return PyUnicode_FromFormat("%S://%S:%i/%S/keys", self->protocol,
        self->host, self->port, self->version_prefix);
}

PRIVATE
PyObject *
Client_get(ClientObject *self, PyObject *args, PyObject *kwds)
{
    static char *kwlist[] = {"key", "quorum", "recursive", "sorted", NULL};
    PyObject *py_key;
    PyObject *result=NULL;
    int quorum = 0, recursive = 0, sorted = 0;
    if (!PyArg_ParseTupleAndKeywords(args, kwds, "|Oppp", kwlist,
                                     &py_key, &quorum, &recursive,
                                     &sorted))
        return NULL;

    PyObject *py_baseurl = Client_url(self, NULL);
    PyObject *py_url = PyUnicode_FromFormat("%S%S?quorum=%s&recursive=%s&sorted=%s",
        py_baseurl, py_key, quorum?"true":"false", recursive?"true":"false",
        sorted?"true":"false");
    Py_XDECREF(py_baseurl);
    char *url = PyUnicode_AsUTF8(py_url);

    CURLcode res;
    CURL *curl;
    struct memory in_chunk = {0};
    curl = curl_easy_init();
    if(curl) {
        curl_easy_setopt(curl, CURLOPT_URL, url);
        curl_easy_setopt(curl, CURLOPT_VERBOSE, VERBOSE);
        curl_easy_setopt(curl, CURLOPT_TIMEOUT, self->read_timeout);

        curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, write_callback);
        curl_easy_setopt(curl, CURLOPT_WRITEDATA, (void *)&in_chunk);
        res = curl_easy_perform(curl);
        if(res != CURLE_OK){
            PyErr_Format(EtcdConnectionFailed, "Communication failed: %s\n",
                  curl_easy_strerror(res));
            goto exit;
        }
        long response_code;
        res = curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &response_code);
        if(res != CURLE_OK){
            PyErr_Format(EtcdConnectionFailed, "Communication failed: %s\n",
                  curl_easy_strerror(res));
            goto exit;
        }
        if(response_code == 404) {
            PyObject *err = EtcdError_FromString(in_chunk.response);
            PyErr_SetObject(EtcdKeyNotFound, err);
            Py_XDECREF(err);
            curl_easy_cleanup(curl);
            goto exit;
        }
        if(response_code != 200) {
            PyErr_Format(EtcdKeyError, "%s", in_chunk.response);
            curl_easy_cleanup(curl);
            goto exit;
        }

        curl_easy_cleanup(curl);
    }
    json_t *root = NULL;
    json_error_t error_json;
    root = json_loads(in_chunk.response, 0, &error_json);
    if(!root) {
        PyErr_Format(EtcdException, "JSON error: on line %d: %s\n%s", error_json.line, error_json.text, in_chunk.response);
        result = NULL;
        goto exit;
    }
    json_t *node = json_object_get(root, "node");
    result=EtcdResult_FromJSON(node);
    json_decref(root);

    exit:
    Py_XDECREF(py_url);
    FREE(in_chunk.response);
    return result;
}

PRIVATE
PyObject *
Client_put(ClientObject *self, PyObject *args, PyObject *kwds)
{
    static char *kwlist[] = {"key", "value", "ttl", NULL};
    PyObject *py_key, *py_value;
    int ttl=-1;

    if (!PyArg_ParseTupleAndKeywords(args, kwds, "|OOi", kwlist,
                                     &py_key, &py_value,
                                     &ttl))
        return NULL;

    PyObject *py_baseurl = Client_url(self, NULL);
    PyObject *py_url = PyUnicode_FromFormat("%S%S", py_baseurl, py_key);
    const char *url=PyUnicode_AsUTF8(py_url);
    Py_XDECREF(py_baseurl);

    struct memory out_chunk = {0}, in_chunk = {0};


    CURLcode res;
    CURL *curl;
    struct curl_slist *list = NULL;
    curl = curl_easy_init();
    if(!curl) {
        PyErr_SetString(PyExc_RuntimeError, "Unable to initialize CURL");
        return NULL;
    }

    Py_ssize_t py_valuelen;
    char *value = PyUnicode_AsUTF8AndSize(py_value, &py_valuelen);
    int valuelen = py_valuelen;
    char *encoded_value = curl_easy_escape(curl, value, valuelen);

    out_chunk.response = malloc(BUFFER_START_LEN);
    if(ttl < 0)
        sprintf(out_chunk.response, "value=");
    else
        sprintf(out_chunk.response, "ttl=%d&value=", ttl);
    int full_len = strlen(out_chunk.response) + strlen(encoded_value);
    if(full_len > BUFFER_START_LEN) {
        out_chunk.response = realloc(out_chunk.response, full_len + 1);
    }
    strcat(out_chunk.response, encoded_value);
    out_chunk.size = full_len;
    curl_free(encoded_value);

    curl_easy_setopt(curl, CURLOPT_URL, url);
    curl_easy_setopt(curl, CURLOPT_VERBOSE, VERBOSE);
    curl_easy_setopt(curl, CURLOPT_READDATA, (void *)&out_chunk);
    curl_easy_setopt(curl, CURLOPT_INFILESIZE, out_chunk.size);
    curl_easy_setopt(curl, CURLOPT_READFUNCTION, read_callback);
    curl_easy_setopt(curl, CURLOPT_UPLOAD, 1L);
    list = curl_slist_append(list, "Expect:");
    list = curl_slist_append(list, "Transfer-Encoding:");
    list = curl_slist_append(list, "Content-Type: application/x-www-form-urlencoded");
    curl_easy_setopt(curl, CURLOPT_HTTPHEADER, list);
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, write_callback);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, (void *)&in_chunk);
    res = curl_easy_perform(curl);
    curl_slist_free_all(list);
    if(res != CURLE_OK) {
        PyErr_Format(EtcdConnectionFailed, "Communication failed: %s\n",
              curl_easy_strerror(res));
        Py_XDECREF(py_url);
        free(out_chunk.response);
        return NULL;
    }
    curl_easy_cleanup(curl);

    PyObject *result = NULL;
    json_t *root = NULL;
    json_error_t error_json;
    root = json_loads(in_chunk.response, 0, &error_json);
    if(!root) {
        PyErr_Format(EtcdException, "JSON error: on line %d: %s\n%s", error_json.line, error_json.text, in_chunk.response);
        goto exit;
    }
    json_t *node = json_object_get(root, "node");
    result=EtcdResult_FromJSON(node);
    json_decref(root);

    exit:
    free(in_chunk.response);
    free(out_chunk.response);
    Py_XDECREF(py_url);
    return result;
}

PRIVATE 
PyObject *
Client_str(PyObject *s)
{
    ClientObject *self = (ClientObject *) s;
    return Client_url(self, NULL);
}

PRIVATE 
PyObject *
Client_repr(PyObject *s)
{
    ClientObject *self = (ClientObject *) s;
    if (self->host == NULL) {
        PyErr_SetString(PyExc_AttributeError, "host");
        return NULL;
    }
    return PyUnicode_FromFormat("<etcd.Client host=%S port=%i protocol=%S>",
        self->host, self->port, self->protocol);
}

PRIVATE 
PyMethodDef Client_methods[] = {
    {"url", (PyCFunction) Client_url, METH_NOARGS,
     "Return the URL. Parameters will be ignored"
    },
    {"put", (PyCFunction) Client_put, METH_VARARGS | METH_KEYWORDS,
     "Sets value for a specified key.\n\
     :param Key:           Expects a String\n\
     :param Value:         Expects a String\n\
     :param ttl(optional): Expects Int - Defaults to None which means that the key will not expire"
    },
    {"get", (PyCFunction) Client_get, METH_VARARGS | METH_KEYWORDS,
     "Gets value for a specified key.\n\
     :param key:                 Expects a String\n\
     :param quorum(optional):    Expects Boolean - Defaults to False\n\
     :param recursive(optional): Expects Boolean - Defaults to False\n\
     :param sorted(optional):    Expects Boolean - Defaults to False"
    },
    {NULL}  /* Sentinel */
};

PRIVATE 
PyMemberDef Client_members[] = {
    {"host", T_OBJECT_EX, offsetof(ClientObject, host), 0,
     "Etcd server name or IP address - Expects String"},
    {"port", T_INT, offsetof(ClientObject, port), 0,
     "Etcd server port - Expects Int"},
    {"protocol", T_OBJECT_EX, offsetof(ClientObject, protocol), 0,
     "Protocol(http/https) - Expects String"},
    {"read_timeout", T_INT, offsetof(ClientObject, read_timeout), 0,
     "Requests timeout - Expects Int"},
    {NULL}  /* Sentinel */
};

PUBLIC
PyTypeObject ClientType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "etcd.Client",
    .tp_doc = PyDoc_STR("Client objects"),
    .tp_basicsize = sizeof(ClientObject),
    .tp_itemsize = 0,
    .tp_flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,
    .tp_new = Client_new,
    .tp_init = (initproc) Client_init,
    .tp_dealloc = (destructor) Client_dealloc,
    .tp_members = Client_members,
    .tp_methods = Client_methods,
    .tp_str = Client_str,
    .tp_repr = Client_repr,
};

PUBLIC
int Client_InitModule(PyObject *m)
{
    if (PyType_Ready(&ClientType) < 0)
        return -1;
    Py_INCREF(&ClientType);
    if (PyModule_AddObject(m, "Client", (PyObject *) &ClientType) < 0) {
        Py_DECREF(&ClientType);
        return -1;
    }
    curl_global_init(CURL_GLOBAL_ALL);
    return 0;
}
