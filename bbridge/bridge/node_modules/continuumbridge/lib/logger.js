
var winston = require('winston');

var levels = {
    levels: {
        silly: 0,
        input: 1,
        verbose: 2,
        prompt: 3,
        debug: 4,
        message: 5,
        message_error: 6,
        authorization: 7,
        info: 8,
        help: 9,
        warn: 10,
        error: 11
    },
    colors: {
        silly: 'magenta',
        input: 'grey',
        verbose: 'cyan',
        prompt: 'grey',
        debug: 'blue',
        message: 'grey',
        message_error: 'yellow',
        authorization: 'magenta',
        info: 'green',
        help: 'cyan',
        warn: 'orange',
        error: 'red'
    }
};

winston.setLevels(levels.levels);
winston.addColors(levels.colors);

var consoleTransport = new (winston.transports.Console)({
    level: 'debug',
    colorize:true,
    silent: false,
    timestamp: true
});

var logger = new (winston.Logger)({
    level: 'debug',
    colorize:true,
    silent: false,
    timestamp: true,
    levels: levels.levels,
    transports: [
        consoleTransport
    ],
    exceptionHandlers: [
        consoleTransport
    ],
    exitOnError: true
});

module.exports = logger;