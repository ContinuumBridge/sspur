
var rest = require('restler'),
    _ = require('underscore'),
    Q = require('q');

var cookie_reader = require('cookie')
    ,errors = require('../errors');

/* Controller Authentication */

var controllerAuth = function(controllerAuthURL, key) {

    var deferredSessionData = Q.defer();

    var authDetailsObj = {
        key: key
    }
    var authDetails = JSON.stringify(authDetailsObj);

    console.log('authDetails', authDetails);
    // Define options for Django REST Client
    var controllerAuthOptions = { 
        method: "post",
        headers: {
            'Content-type': 'application/json', 
            'Accept': 'application/json'
        },
        data: authDetails
    };  

    // Make a request to Django to get session data
    rest.post(controllerAuthURL, controllerAuthOptions).on('complete', function(data, response) {

        // If the response was good, return the session data
        if (response && response.hasOwnProperty('statusCode')) { 
            if (response.statusCode == 200) {
                console.log('Response headers are', response.headers['set-cookie']);
                _.forEach(response.headers['set-cookie'], function(rawCookie) {

                    var cookie = cookie_reader.parse(String(rawCookie));
                    console.log('Cookie is', cookie);
                    if (cookie['sessionid']) {
                        data.sessionID = cookie['sessionid'];
                        deferredSessionData.resolve(data);
                    }
                });
                //var cookies = cookieParser.JSONCookies(String(response.headers['set-cookie']));
                //deferredSessionData.resolve(cookies);
                //console.log('Cookies are is', cookies);
            } else {
                //console.log('error response is', Object.keys(response));
                //console.log('error data is', data);
                var error = new errors.AuthorizationError(response);
                deferredSessionData.reject(error);
            }
        } else {
            deferredSessionData.reject('There was an error authenticating to the Controller');
        }   
    });

    return deferredSessionData.promise;
}

module.exports = controllerAuth;

