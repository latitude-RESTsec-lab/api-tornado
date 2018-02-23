# -*- coding: utf-8 -*-
"""
Created on Fri Jan 19 09:46:12 2018

"""

import json
import tornado.web
from datetime import datetime
import re
import logging
import db.db as db

def validate_suported_mime_type(request):
    if 'Accept' in request.headers:
        if request.headers['Accept'] == '*/*':
            return True
        else:
            return request.headers['Accept'] == 'application/json'
    else:
        return True

# stores all database configuration
database_config = {}

# operations to be registered in the application object


def configure_params(p_servername, p_database, p_username, p_password):
    database_config['db_servername'] = p_servername
    database_config['db_database'] = p_database
    database_config['db_username'] = p_username
    database_config['db_password'] = p_password

# web service API servidores
class get_all_employees_api(tornado.web.RequestHandler):
    def get(self):
        dados = db.get_all_employees(database_config)
        self.set_header("Content-Type", "application/json")
        self.write(json.dumps(dados))
        self.set_status(200)
        self.finish()
        
# web service API servidor/{matricula}@
class get_employee_by_id_api(tornado.web.RequestHandler):
    def get(self, mat):
        if not validate_suported_mime_type(self.request):
            return "Unsupported Media Type", 415
        else:
            if mat:
                # retrieve one specific employee
                dados = db.get_employee_by_id(database_config, mat)
                if dados:
                    self.set_header("Content-Type", "application/json")
                    self.write(json.dumps(dados))
                    self.set_status(200)
                    self.finish()
                else:
                    self.set_status(404)
                    self.finish()
            else:
                self.set_status(400)
                self.finish()

# web service - create new employee
class create_a_new_employee_api(tornado.web.RequestHandler):
    def post(self):
        '''API to create a new employee record using the provided data.

        Requires JSON formatted request containing the employ data listed 
        below in the sample_json var.
        
        Example: 
        curl -H "Content-Type: application/json" -X POST -d '{"id_servidor": 4321, "siape": 123456, "id_pessoa": 1234, "matricula_interna": 54321, "nome": "João da Silva", "nome_identificacao": "João Ident", "data_nascimento": "1970-01-31", "sexo": "M"}' http://localhost:8000/api/servidor/
        
        sample_json = {
        "id_servidor": 4321,
        "siape": 123456,
        "id_pessoa": 1234,
        "matricula_interna": 54321,
        "nome": "João da Silva",
        "nome_identificacao": "João Ident",
        "data_nascimento": "1970-01-31",
        "sexo": "M"
    }
        '''
        if not validate_suported_mime_type(self.request):
            self.set_status(415)
            self.finish()
            
        # TODO test if the data is JSON
        new_employee_data = json.loads(self.request.body)
        print("Received data: {}".format(new_employee_data))

        data_validation = dict()
        # - required data
        data_validation['required'] = required_data_validator(new_employee_data)
        # - size validator: nome, sexo
        data_validation['size'] = data_size_validator(new_employee_data)
        # - domain validator: sexo
        data_validation['domain'] = data_domain_validator(new_employee_data)
        # - business validator: data_nascimento
        data_validation['business'] = business_rule_validator(new_employee_data)
        # - regex validator: date (data_nascimento), int (id_servidor, siape, id_pessoa)
        data_validation['regex'] = regex_validator(new_employee_data)

        msg = ";\n".join(list(str(v) for k, v in data_validation.items() if v))
        if msg:
            self.set_header("Content-Type", "text/plain")
            self.write("Bad request.\n{}.".format(msg))
            self.set_status(400)
            self.finish()

        # storing data in the database
        new_id = db.create_employee(database_config, new_employee_data)
        if new_id:
            self.set_header("Content-Type", "text/plain")
            self.set_header("Location", '/api/servidor/{}'.format(new_id))
            self.set_status(201)
            self.finish()
        else:
            self.set_status(500)
            self.write("Bad request.\n{}.".format(msg))
            self.finish()

def regex_validator(employee_data):
    '''Function to validate if a subset of fields has accepted pattern.

    parameter
        - employee_data: a dict with the reveived data.

    returns
        - Empty object: if it is all ok
        - Message with the fields with wrong values: if is not ok
	'''
    INT_VALIDATION_PATTERN = r'\b[0-9]+\b'
    DATE_VALIDATION_PATTERN = r'^(19[0-9]{2}|2[0-9]{3})-(0[1-9]|1[012])-([123]0|[012][1-9]|31)$'
    NOME_VALIDATION_PATTERN = r'^([A-Z][a-z]+([ ]?[a-z]?[\'-]?[A-Z][a-z]+)*)$'

    result = []

    for x in ['id_servidor', 'siape', 'id_pessoa']:
        if x in employee_data and not re.search(INT_VALIDATION_PATTERN, str(employee_data[x])):
            result.append("'{}' is an unaccepted pattern for the field '{}'".format(employee_data[x], x))

    for x in ['data_nascimento']:
        if x in employee_data and not re.search(DATE_VALIDATION_PATTERN, str(employee_data[x])):
            result.append("'{}' is an unaccepted pattern for the field '{}'".format(employee_data[x], x))

    for x in ['nome', 'nome_identificacao']:
        if x in employee_data and not re.search(NOME_VALIDATION_PATTERN, str(employee_data[x])):
            result.append("'{}' is an unaccepted pattern for the field '{}'".format(employee_data[x], x))

    return "; ".join(result)

def business_rule_validator(employee_data):
    '''Function to validate if the data respects defined business rules.

    parameter
        - employee_data: a dict with the reveived data.

    returns
        - Empty object: if it is all ok
        - Message with the fields with wrong values: if is not ok
	'''
    result = []
    
    if 'data_nascimento' in employee_data:
        try:
            data_nascimento = datetime.strptime(employee_data['data_nascimento'], '%Y-%m-%d')
            if data_nascimento > datetime.now():
                result.append("Field '{}' has an unaccepted value: {}".format('data_nascimento', 'this date should be in the past'))
        except:
            pass

    return "; ".join(result)

def data_domain_validator(employee_data):
    '''Function to validate if a subset of fields has accepted values.

    parameter
        - employee_data: a dict with the reveived data.

    returns
        - Empty object: if it is all ok
        - Message with the fields with wrong data: if is not ok
	'''
    result = []
    domain_data = [('sexo', {'F', 'M'})]
    for x in domain_data:
        if employee_data[x[0]] not in x[1]:
            result.append("'{}' is an unaccepted value for the field '{}'".format(employee_data[x[0]], x[0]))
    return "; ".join(result)

def data_size_validator(employee_data):
    '''Function to validate if a subset of fields is in an accepted size.

    parameter
        - employee_data: a dict with the reveived data.

    returns
        - Empty object: if it is all ok
        - Message with the fields in a wrong size: if is not ok
	'''
    result = []
    data_size = [('nome', 100), ('sexo', 1)]
    for x in data_size:
        if x[0] in employee_data and len(employee_data[x[0]]) > x[1]:
            result.append("Field '{}' is {} size long but it must be {}".format(x[0], len(employee_data[x[0]]), x[1]))
    return "; ".join(result)

def required_data_validator(employee_data):
    '''Function to validate if all required data is present.

    parameter
        - employee_data: a dict with the reveived data.

    returns
        - Empty object: if it is all ok
        - Message with the missing fields: if is not ok
	'''
    required_data = ['nome', 'nome_identificacao', 'siape', 'data_nascimento', 'sexo', 'id_servidor', 'id_pessoa']
    diff_result = set(required_data) - set(employee_data)

    if not diff_result:
        return None
    else:
        message = "This required data is missing: {}".format("; ".join(diff_result))
        return message
