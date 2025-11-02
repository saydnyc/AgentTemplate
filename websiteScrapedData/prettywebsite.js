// Webpack Runtime Bootstrap (Deobfuscated Version)
// This script handles dynamic loading and management of JS and CSS chunks
// in a Webpack-built application. It ensures efficient code-splitting and
// async loading while managing dependencies.

(function(modules) {
  var installedModules = {};
  var installedChunks = { 77: 0 }; // 77 is the main chunk
  var chunkStatus = { 77: 0 };
  var chunkQueue = [];

  function __webpack_require__(moduleId) {
    if (installedModules[moduleId]) return installedModules[moduleId].exports;

    var module = installedModules[moduleId] = {
      i: moduleId,
      l: false,
      exports: {}
    };

    modules[moduleId].call(module.exports, module, module.exports, __webpack_require__);

    module.l = true;
    return module.exports;
  }

  function loadChunk(chunkId) {
    var promises = [];

    if (chunkStatus[chunkId]) {
      promises.push(chunkStatus[chunkId]);
    } else if (chunkStatus[chunkId] !== 0) {
      var promise = new Promise((resolve, reject) => {
        chunkStatus[chunkId] = [resolve, reject];
      });
      promises.push(chunkStatus[chunkId][2] = promise);

      var script = document.createElement('script');
      script.charset = 'utf-8';
      script.timeout = 120000;
      script.src = __webpack_require__.p + chunkId + '.chunk.js';

      var error = new Error();
      script.onerror = script.onload = function(event) {
        clearTimeout(timeout);
        var chunk = chunkStatus[chunkId];
        if (chunk !== 0) {
          if (chunk) {
            var type = event && (event.type === 'load' ? 'missing' : event.type);
            var request = event && event.target && event.target.src;
            error.message = 'Loading chunk ' + chunkId + ' failed.
(' + type + ': ' + request + ')';
            error.name = 'ChunkLoadError';
            error.type = type;
            error.request = request;
            chunk[1](error);
          }
          chunkStatus[chunkId] = undefined;
        }
      };
      var timeout = setTimeout(function() {
        script.onerror({ type: 'timeout', target: script });
      }, 120000);

      document.head.appendChild(script);
    }

    return Promise.all(promises);
  }

  function checkDeferredModules() {
    var result;
    for (var i = 0; i < chunkQueue.length; i++) {
      var deferredModule = chunkQueue[i];
      var fulfilled = true;
      for (var j = 1; j < deferredModule.length; j++) {
        var depId = deferredModule[j];
        if (installedChunks[depId] !== 0) fulfilled = false;
      }
      if (fulfilled) {
        chunkQueue.splice(i--, 1);
        result = __webpack_require__(__webpack_require__.s = deferredModule[0]);
      }
    }
    return result;
  }

  __webpack_require__.e = loadChunk;
  __webpack_require__.m = modules;
  __webpack_require__.c = installedModules;
  __webpack_require__.p = 'https://cdn2.edulastic.com/JS/dist/';

  var jsonpArray = this.webpackJsonpedulastic = this.webpackJsonpedulastic || [];
  var oldJsonpFunction = jsonpArray.push.bind(jsonpArray);
  jsonpArray.push = function(chunkData) {
    var chunkIds = chunkData[0];
    var moreModules = chunkData[1];
    var executeModules = chunkData[2];

    for (var i = 0; i < chunkIds.length; i++) {
      var chunkId = chunkIds[i];
      if (Object.prototype.hasOwnProperty.call(installedChunks, chunkId) && installedChunks[chunkId]) {
        installedChunks[chunkId][0]();
      }
      installedChunks[chunkId] = 0;
    }

    for (var moduleId in moreModules) {
      if (Object.prototype.hasOwnProperty.call(moreModules, moduleId)) {
        modules[moduleId] = moreModules[moduleId];
      }
    }

    if (oldJsonpFunction) oldJsonpFunction(chunkData);
    while (chunkQueue.length) {
      checkDeferredModules();
    }

    return __webpack_require__(executeModules);
  };

  checkDeferredModules();
})([]);

// Additional scripts at the bottom of the original file load other chunks:
// <script src="https://cdn2.edulastic.com/JS/dist/vendor-react.e037fd13.chunk.js"></script>
// <script src="https://cdn2.edulastic.com/JS/dist/vendor-common.66a6ce49.chunk.js"></script>
// ... (many more)
