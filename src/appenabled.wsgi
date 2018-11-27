from cgi import parse_qs, escape
from pymongo import MongoClient

def application(environ, start_response):
    query = parse_qs(environ['QUERY_STRING'])
    #app_name="Amos_Invoice_Manager"
    app_name = query.get("ApplicationName", [ None ])[0]
    ddc = query.get("ddc", [ "SMYPXENDDC03V" ])[0]
    citrix = MongoClient().citrix
    app_data = citrix[ddc].apps.find_one({"ApplicationName": app_name})
    if app_data is not None and 'Enabled' in app_data:
        output = str(app_data['Enabled'])
    else:
        output = "NotFound %s" % app_name
        
    status = '200 OK'
    response_headers = [('Content-type', 'text/plain'),
                    ('Content-Length', str(len(output)))]

    start_response(status, response_headers)
    
    return output

