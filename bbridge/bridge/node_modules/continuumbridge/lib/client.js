
require('./config');

var _ = require('underscore');

var retry = require('retry')
    ,util = require('util');

var CBSocketWrapper = require('./cbSocket/socket.js')
    ,controllerAuth = require('./cbSocket/auth.js')
    ,Message = require('./message')
    ;

var logger = require('./logger');

/* Node concentrator for managing socket communication between Client and the main server (Controller) */

var Client = function(options) {

    var self = this;

    this.connected = false;

    this.config = _.defaults(options, {
        cbAPI: CONTROLLER_API
    });
    var cbSocketIP = options.cbSocket || CONTROLLER_SOCKET;
    this.config.cbSocket = options.bridge ? cbSocketIP + ':9416/' : cbSocketIP + ":7521/";

    this.cbSocketWrapper = new CBSocketWrapper(this.config);

    this.cbSocketWrapper.on('connect', function(message) {
        self.connected = true;
        self.emit('connect');
        logger.log('debug', 'Client connect');
    });

    this.cbSocketWrapper.on('disconnect', function(message) {
        self.connected = false;
        self.emit('disconnect');
    });

    this.cbSocketWrapper.on('message', function(message) {

        self.emit('message', message);

        var source = message.get('source');
        self.emit(source, message);
        //logger.info('CB => Client: ', message)
    });

    // Restart connection process on 'giveUp'
    this.cbSocketWrapper.on('fail', function() {
        self.cbSocketWrapper.giveUp();
        self.connect();
    });

    this.faultTolerantAuth = retry.operation()

    this.connect();
}

var EventEmitter = require('events').EventEmitter;
util.inherits(Client, EventEmitter);

Client.prototype.connect = function() {

    var self = this;
    var config = this.config;

    this.faultTolerantAuth.attempt(function(currentAttempt) {

        var controllerAuthURL = config.bridge ? config.cbAPI + 'bridge_auth/login/'
            : config.cbAPI + 'client_auth/login/';

        controllerAuth(controllerAuthURL, config.key).then(function(authData) {

            logger.info('Authenticated to Client Controller');
            self.setConfig(authData);
            self.cbSocketWrapper.connect(authData.sessionID);

        }, function(error) {

            logger.error(error);
            self.faultTolerantAuth.retry(error);
            logger.info('Retrying..');
            // Authorise again after backoff
        })
    });
}

Client.prototype.setConfig = function(authData) {

    this.cbid = authData.cbid;
}

Client.prototype.publish = function(message) {

    if (this.cbSocketWrapper.socket) {
        var jsonMessage = message instanceof Message ? message.toJSONString() : message;
        this.cbSocketWrapper.socket.emit('message', jsonMessage);
    }
}

module.exports = Client;