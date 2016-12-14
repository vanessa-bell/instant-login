""" Clever Instant Login implementation """
# Built on Clever's Python example:
# https://github.com/Clever/clever-oauth-examples/tree/master/python

import base64
import json
import os
import urllib
import requests

from bottle import app, redirect, request, route, hook, run, template
from beaker.middleware import SessionMiddleware

# Use your Client ID and secret from the app in your Clever developer dashboard:
# https://account.clever.com/partner/applications
CLIENT_ID = os.environ['CLIENT_ID']
CLIENT_SECRET = os.environ['CLIENT_SECRET']

if 'PORT' in os.environ:
    PORT = os.environ['PORT']
else:
    PORT = 5000

# Remember to register redirect URIs with the appropriate app on your developer dashboard here:
# https://apps.clever.com/partner/applications/
# If using the default PORT set above, make sure to register "http://localhost:5000/oauth"

REDIRECT_URI = 'https://damp-caverns-13079.herokuapp.com/oauth'
CLEVER_OAUTH_URL = 'https://clever.com/oauth/tokens'
CLEVER_API_BASE = 'https://api.clever.com'

# Use the bottle session middleware to store an object to represent a "logged in" state.
SESSION_OPTS = {
    'session.type': 'memory',
    'session.cookie_expires': 300,
    'session.data_dir': './session/',
    'session.auto': True
}
MYAPP = SessionMiddleware(app(), SESSION_OPTS)

@hook('before_request')
def setup_request():
    request.session = request.environ['beaker.session']

 ################################## ROUTES ##################################

@route('/')
def index():
    """ Home page route creates a Clever Instant Login button. """
    encoded_string = urllib.urlencode({
        'response_type': 'code',
        'redirect_uri': REDIRECT_URI,
        'client_id': CLIENT_ID,
        'scope': 'read:user_id read:sis'
        })
    return template("<h1>Login with Instant Login<br/><br/> \
            <a href='https://clever.com/oauth/authorize?" + encoded_string +
                    "'><img src='http://assets.clever.com/sign-in-with-clever/sign-in-with-clever-small.png'/></a></h1>"
                   )

# The OAuth 2.0 redirect URI location must match what was set above as the REDIRECT_URI
# When this route is executed, the "code" parameter is received and then exchanged for a Clever access token.
# After receiving the access token, it is used with api.clever.com/me to determine the owner (user)
# Then the session state is saved, and the user is redirected to the application

@route('/oauth')
def oauth():
    code = request.query.code

    payload = {
        'code': code,
        'grant_type': 'authorization_code',
        'redirect_uri': REDIRECT_URI
    }

    headers = {
        'Authorization': 'Basic {base64string}'.format(base64string=base64.b64encode(CLIENT_ID + ':' + CLIENT_SECRET)), 'Content-Type': 'application/json'
    }

# Don't forget to handle 4xx and 5xx errors!
    response = requests.post(CLEVER_OAUTH_URL, data=json.dumps(payload), headers=headers).json()
    token = response['access_token']

    bearer_headers = {
        'Authorization': 'Bearer {token}'.format(token=token)
    }

# Don't forget to handle 4xx and 5xx errors!
    result = requests.get(CLEVER_API_BASE + '/me', headers=bearer_headers).json()
    data = result['data']

# Only handle student and teacher logins for our app (other types include districts)
    if data['type'] == 'district_admin':
        return template("Sorry, you must be a student or teacher to log in to this app but you are a district administrator.")
    else:
        if 'name' in data: #SIS scope
            nameObject = data['name']

        if data['type'] == 'teacher':
            teacherId = data['id']
            teacher = requests.get(CLEVER_API_BASE + '/v1.1/teachers/{teacherId}'.format(teacherId=teacherId),
                                   headers=bearer_headers).json()

            nameObject = teacher['data']['name']

            request.session['nameObject'] = nameObject
            request.session['type'] = data['type']

            redirect('/app')

        else:
            studentId = data['id']
            student = requests.get(CLEVER_API_BASE + '/v1.1/students/{studentId}'.format(studentId=studentId),
                                   headers=bearer_headers).json()
            nameObject = student['data']['name']

        request.session['nameObject'] = nameObject
        request.session['type'] = data['type']

        redirect('/app')

@route('/app')
def app():
    """ app logic -- only for users who've been authenticated and identified"""
    if 'nameObject' in request.session:
        nameObject = request.session['nameObject']
        userType = request.session['type']
        return template("You are now logged in as {{name}}. You are a {{type}}. Click <a href='/logout'>here</a> to logout", name=nameObject['first'] + ' ' + nameObject['middle'] + ' ' + nameObject['last'], type=userType)
    else:
        return "You must be logged in to see this page. Click <a href='/'>here</a> to log in."

@route('/logout')
def logout():
    """ simple logout route """
    if not request.session:
        redirect('/')
    else:
        request.session.delete()
        redirect('/')


if __name__ == '__main__':
    run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
