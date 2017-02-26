
var util = require('util')

var AuthorizationError = function(response) {
    this.name = "AuthorizationError";

    var res = response || {};
    var req = res.req || {};
    var httpVersion = util.format('HTTP/%s.%s', res.httpVersionMajor, res.httpVersionMinor);
    var message = util.format('"%s %s %s" %s', req.method, req.path, httpVersion, res.statusCode);

    this.message = (message || "");
    this.response = (res.rawEncoded || "");
}

AuthorizationError.prototype = Error.prototype;

module.exports.AuthorizationError = AuthorizationError;

Unauthorized = function(message) {
    this.name = "Unauthorized";
    this.message = (message || "");
}
Unauthorized.prototype = Error.prototype;

module.exports.Unauthorized = Unauthorized;

