

var _ = require('underscore')
    ,logger = require('./logger')
    ;

// Create local references to array methods we'll want to use later.
var array = [];
var slice = array.slice;

Message = function(attributes, options) {

    var unknownAttrs = attributes || {};
    attrs = (typeof(unknownAttrs) == 'string') ? JSON.parse(unknownAttrs) : unknownAttrs;
    options || (options = {});
    this.attributes = {};
    //if (options.parse) attrs = this.parse(attrs, options) || {};
    //attrs = _.defaults({}, attrs, _.result(this, 'defaults'));
    this.set(attrs, options);
    this.changed = {};
    this.initialize.apply(this, arguments);
};

_.extend(Message.prototype, {

    // Initialize is an empty function by default. Override it with your own
    // initialization logic.
    initialize: function(){},

    toJSON: function(options) {
      return _.clone(this.attributes);
    },

    // Return a copy of the model's `attributes` object.
    toJSONString: function(options) {

        var jsonAttributes = JSON.stringify(_.clone(this.attributes));
        return jsonAttributes;
    },

    setJSON: function(jsonAttributes, options) {

        if (typeof jsonAttributes == 'string') {
            try {
                var attributes = JSON.parse(jsonAttributes);
            } catch (error) {
                logger.error(error);
            }
        } else if (typeof jsonAttributes == 'object') {
            var attributes = jsonAttributes;
        }

        if (!options) options = {};

        this.set(attributes, options);
    },

    returnToSource: function(source) {

        // Switches the original source to the destination
        var src = source || "";
        var prevSource = this.get('source') || "";
        this.set('destination', prevSource);
        this.set('source', src);
    },

    returnError: function(error) {

    },

    // Get the value of an attribute.
    get: function(attr) {
      return this.attributes[attr];
    },

    set: function(key, val, options) {
      var attr, attrs, unset, changes, silent, changing, prev, current;
      if (key == null) return this;

      // Handle both `"key", value` and `{key: value}` -style arguments.
      if (typeof key === 'object') {
        attrs = key;
        options = val;
      } else {
        (attrs = {})[key] = val;
      }

      options || (options = {});

      // Run validation.
      if (!this._validate(attrs, options)) return false;

      // Extract attributes and options.
      unset           = options.unset;
      silent          = options.silent;
      changes         = [];
      changing        = this._changing;
      this._changing  = true;

      if (!changing) {
        this._previousAttributes = _.clone(this.attributes);
        this.changed = {};
      }
      current = this.attributes, prev = this._previousAttributes;

      // For each `set` attribute, update or delete the current value.
      for (attr in attrs) {
        val = attrs[attr];
        if (!_.isEqual(current[attr], val)) changes.push(attr);
        if (!_.isEqual(prev[attr], val)) {
          this.changed[attr] = val;
        } else {
          delete this.changed[attr];
        }
        unset ? delete current[attr] : current[attr] = val;
      }

      this._pending = false;
      this._changing = false;
      return this;
    },

    unset: function(attr, options) {
      return this.set(attr, void 0, _.extend({}, options, {unset: true}));
    },

    _validate: function(attrs, options) {
      if (!options.validate || !this.validate) return true;
      attrs = _.extend({}, this.attributes, attrs);
      var error = this.validationError = this.validate(attrs, options) || null;
      if (!error) return true;
      this.trigger('invalid', this, error, _.extend(options, {validationError: error}));
      return false;
    }

})

/*
// Underscore methods that we want to implement on the Model.
var modelMethods = ['keys', 'values', 'pairs', 'invert', 'pick', 'omit'];

// Mix in each Underscore method as a proxy to `Model#attributes`.
_.each(modelMethods, function(method) {
  if (!_[method]) return;
    Message.prototype[method] = function() {
      var args = slice.call(arguments);
      args.unshift(this.attributes);
      return _[method].apply(_, args);
    };
});

*/

module.exports = Message;
