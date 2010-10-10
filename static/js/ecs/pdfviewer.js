ecs.pdfviewer = {
    /* TODO: optimize loading time / responsiveness
     - Guess which images might be accessed next and preload them in the background.
       At least firefox has a default connection limit per server of 15.
     - Reuse page <div>s
     - Optional: use larger sprites
     */
    ImageSet: new Class({
        initialize: function(options){
            this.sprite = options.sprite;
            this.width = options.width;
            this.height = options.height;
            this.images = [];
        },
        addImage: function(image){
            if(!this.height){
                this.height = image.height;
                this.width = image.width;
            }
            this.images.push(image);
        },
        loadImage: function(image, callback){
            var img = new Image();
            img.addEvent('load', function(){
                if(callback){
                    callback();
                }
            });
            img.src = image.url;
        },
        getSpriteOffset: function(x, y){
            return '-' + parseInt(x * this.getPageWidth()) + 'px -' + parseInt(y * this.getPageHeight()) + 'px';
        },
        getPageWidth: function(){
            return this.width / this.sprite.x;
        },
        getPageHeight: function(){
            return this.height / this.sprite.y;
        },
        renderPage: function(pageIndex, callback){
            var el = new Element('div', {'class': 'loading'});
            el.store('pageIndex', pageIndex);
            var perImage = this.sprite.x * this.sprite.y;
            var imageIndex = parseInt(pageIndex / perImage);
            var spriteIndex = pageIndex % perImage;
            var spriteX = spriteIndex % this.sprite.x;
            var spriteY = parseInt(spriteIndex / this.sprite.x);
            var image = this.images[imageIndex];
            el.setStyles({
                'width': this.getPageWidth() + 'px',
                'height': this.getPageHeight() + 'px'
            });
            var offset = this.getSpriteOffset(spriteX, spriteY);
            this.loadImage(image, function(){
                el.removeClass('loading');
                el.setStyles({
                    'background-image': 'url(' + image.url + ')',
                    'background-position': offset
                });
                if(callback){
                    callback(el);
                }
            });
            return el;
        }
    }),
    
    utils: {
        isAtBottom: function(){
            var win = $(window);
            // we have to use <= 0, because firefox somehow manages to scroll one pixel beyond the window.
            return win.getScrollHeight() - win.getScroll().y - win.getHeight() <= 0;
        },
        isAtTop: function(){
            return $(window).getScroll().y == 0
        }
    },

    DocumentViewer: new Class({
        initialize: function(el, options){
            this.element = $(el);
            this.pageCount = options.pageCount;
            this.controllers = options.controllers;
            this.wheelThreshold = options.wheelThreshold || 30.0;
            this.title = options.title;
            this.helpContents = options.helpContents;
            this.searchURL = options.searchURL;
            this.editAnnotationURL = options.editAnnotationURL;
            this.deleteAnnotationURL = options.deleteAnnotationURL;
            this.metaKey = options.metaKey || '';
            this.keyboardNavigationEnabled = true;

            this.imageSets = {};
            this.currentPageIndex = 0;
            this.currentControllerIndex = 0;
            this.currentScreen = null;
            this.currentRenderArgs = [];

            this._wheelCounter = 0;
            this._wheelTimeout = null;
            this._wheelReset = (function(){this._wheelCounter = 0; this._wheelTimeout = null;}).bind(this);
            $(window).addEvent('click', this.handleClick.bind(this));
            $(window).addEvent('mousewheel', this.handleMouseWheel.bind(this));
            $(window).addEvent('keydown', this.handleKeyPress.bind(this));
            
            this.body = new Element('div', {'class': 'body'});
            this.viewport = new Element('div', {'class': 'viewport'});
            this.header = new Element('div', {'class': 'header', html: this.title});
            this.prevLink = new Element('a', {'class': 'previous', html: '<b>previous</b>'});
            this.nextLink = new Element('a', {'class': 'next', html: '<b>next</b>'});
            this.element.grab(this.header);
            this.element.grab(this.body);
            this.body.grab(this.prevLink);
            this.body.grab(this.viewport);
            this.body.grab(this.nextLink);
            this.prevLink.addEvent('click', (function(){
                this.previousPage();
            }).bind(this));
            this.nextLink.addEvent('click', (function(){
                this.nextPage();
            }).bind(this));

            this.annotations = $H({});
            this.annotationMode = false;
            this.annotationOverlay = new Element('div', {'class': 'annotationOverlay'})
            this.annotationEditor = new ecs.pdfviewer.AnnotationEditor(this);
            
            var disableKeyNav = (function(){this.keyboardNavigationEnabled = false;}).bind(this)
            var enableKeyNav = (function(){this.keyboardNavigationEnabled = true;}).bind(this)
            this.annotationEditor.addEvent('show', disableKeyNav);
            this.annotationEditor.addEvent('hide', enableKeyNav);
            
            this.searchPopup = new ecs.pdfviewer.SearchPopup(this);
            this.searchPopup.addEvent('show', disableKeyNav);
            this.searchPopup.addEvent('hide', enableKeyNav);
            
        },
        gotoAnchor: function(hash){
            hash = hash || window.location.hash;
            if(hash){
                this.setPage(parseInt(hash.substring(1)) - 1, false);
                this.setControllerIndex(this.controllers.length - 1);
            }
        },
        setMetaKey: function(meta){
            this.metaKey = meta;
        },
        getImageSetKey: function(x, y){
            return x + 'x' + y;
        },
        addImageSet: function(imageSet){
            var key = this.getImageSetKey(imageSet.sprite.x, imageSet.sprite.y);
            this.imageSets[key] = imageSet;
        },
        addImage: function(image){
            var imageSet = this.imageSets[this.getImageSetKey(image.tx, image.ty)];
            if(!imageSet){
                dbug.log("dropping image: ", image);
                return;
            }
            imageSet.addImage(image);
        },
        getController: function(){
            return this.controllers[this.currentControllerIndex];
        },
        update: function(){
            this.getController().render(this, this.currentPageIndex);
        },
        setControllerIndex: function(index){
            this.currentControllerIndex = index;
            this.update();
        },
        cycleController: function(delta){
            index = (this.controllers.length + this.currentControllerIndex + (delta || 1)) % this.controllers.length
            this.setControllerIndex(index);
        },
        setPage: function(pageIndex, update){
            if(pageIndex != this.currentPageIndex){
                this.currentPageIndex = pageIndex;
                if(update !== false){
                    this.update();
                }
            }
        },
        nextPage: function(delta){
            $(document.body).scrollTo(0, 0);
            this.setPage(Math.min(this.currentPageIndex + (delta || this.getController().sliceLength), this.pageCount - 1));
        },
        previousPage: function(delta){
            this.setPage(Math.max(this.currentPageIndex - (delta || this.getController().sliceLength), 0));
        },
        addAnnotation: function(pageIndex, annotation){
            var key = '_' + pageIndex;
            if(!this.annotations[key]){
                this.annotations[key] = [];
            }
            this.annotations[key].push(annotation);
        },
        removeAnnotation: function(annotationElement){
            var annotation = annotationElement.retrieve('annotation');
            this.annotations.each(function(annotations){
                annotations.erase(annotation);
            });
            if(this.annotationMode){
                annotation.endAnnotationMode(annotationElement);
            }
            annotationElement.dispose();
            if(!annotation.pk){
                return;
            }
            var request = new Request({
                url: this.deleteAnnotationURL,
                method: 'post',
                data: 'pk=' + annotation.pk
            });
            request.send();
        },
        sendAnnotationUpdate: function(annotation){
            var request = new Request({
                url: this.editAnnotationURL,
                method: 'post',
                data: $H({
                    pk: annotation.pk,
                    x: annotation.x,
                    y: annotation.y,
                    width: annotation.w,
                    height: annotation.h,
                    text: annotation.text,
                    page_number: this.currentPageIndex + 1
                }).toQueryString()
            });
            request.send();
        },
        getAnnotations: function(pageIndex){
            return this.annotations['_' + pageIndex] || [];
        },
        renderAnnotation: function(pageEl, annotation){
            var annotationElement = annotation.attachTo(pageEl, (function(){
                this.annotationEditor.show(annotation, annotationElement);
            }).bind(this));
            annotationElement.store('annotation', annotation);
            return annotationElement;
        },
        render: function(imageSetKey, offset, w, h){
            if($A(arguments).every((function(val, i){ return val == this.currentRenderArgs[i]}).bind(this))){
                return;
            }
            this.currentRenderArgs = $A(arguments);
            window.location.hash = this.currentPageIndex + 1;
            this.header.innerHTML = this.title + ' <span class="location">Seite ' + (offset + 1) + (w*h > 1 ? ' - ' + (offset + w*h) : '') + ' von ' + this.pageCount + '</span>';
            var imageSet = this.imageSets[imageSetKey];
            if(this.currentScreen){
                this.currentScreen.dispose();
            }
            var screen = new Element('div', {'class': 'screen'});
            for(var y = 0; y < h; y++){
                var row = new Element('div', {'class': 'row'});
                for(var x = 0; x < w; x++){
                    var pageIndex = offset + y*w + x;
                    if(pageIndex >= this.pageCount){
                        break;
                    }
                    var pageEl = imageSet.renderPage(pageIndex, (function(pageEl){
                        this.getAnnotations(pageEl.retrieve('pageIndex')).each((function(annotation){
                            this.renderAnnotation(pageEl, annotation);
                        }).bind(this));
                    }).bind(this));
                    pageEl.addClass('page');
                    pageEl.id = 'p' + imageSetKey + '_' + pageIndex;
                    if(pageIndex == this.currentPageIndex){
                        pageEl.addClass('current');
                    }
                    pageEl.grab(new Element('div', {'class': 'info', html: 'Seite ' + (pageIndex + 1)}));
                    row.grab(pageEl);
                }
                screen.grab(row);
            }
            this.viewport.grab(screen);
            this.currentScreen = screen;
            return screen;
        },
        toggleAnnotationMode: function(){
            if(this.getController().sliceLength != 1){
                return;
            }
            var am = this.annotationMode = !this.annotationMode;
            var pageEl = this.currentScreen.getElement('.page');
            this.nextLink.setStyle('display', am ? 'none' : '');
            this.prevLink.setStyle('display', am ? 'none' : '');
            pageEl[am ? 'appendChild' : 'removeChild'](this.annotationOverlay);
            if(!this.annotationMode){
                pageEl.getChildren('.annotation').each((function(annotationElement){
                    var annotation = annotationElement.retrieve('annotation');
                    annotation.endAnnotationMode(annotationElement);
                    this.sendAnnotationUpdate(annotation);
                }).bind(this));
            }
            else{
                pageEl.getChildren('.annotation').each(function(annotationElement){
                    var annotation = annotationElement.retrieve('annotation');
                    annotation.startAnnotationMode(annotationElement);
                });
            }
        },
        handleKeyPress: function(e){
            if(!this.keyboardNavigationEnabled){
                return true;
            }
            var metaKey = !this.metaKey || e[this.metaKey];
            var U = ecs.pdfviewer.utils;
            var atTop = U.isAtTop();
            var atBottom = U.isAtBottom();

            if(e.key == 'space'){
                this.helpContents.toggleClass('hidden');
                return false;
            }
            if(metaKey && e.key == 'a' && this.getController().options.showAnnotations){
                this.toggleAnnotationMode();
                return false;
            }
            
            if(metaKey && (e.key == 's' || e.key == 'f')){
                this.searchPopup.show();
                return false;
            }
            
            if(this.annotationMode && e.key == 'esc'){
                this.toggleAnnotationMode();
                return;
            }
            if(this.annotationMode){
                return;
            }

            if(e.key == 'enter'){
                this.cycleController(+1);
                return false;
            }
            else if(e.key == 'up'){
                if(metaKey){
                    this.cycleController(-1);
                }
                else if(atTop){
                    this.previousPage(this.getController().sliceLength);
                }
                else{
                    return true;
                }
                return false;
            }
            else if(e.key == 'down'){
                if(metaKey){
                    this.cycleController(+1);
                }
                else if(atBottom){
                    this.nextPage();
                }
                else{
                    return true;
                }
                return false;
            }
            else if(metaKey && e.key == 'right'){
                if(e.shift){
                    this.setPage(this.pageCount - 1);
                }
                else{
                    this.nextPage();
                }
                return false;
            }
            else if(metaKey && e.key == 'left'){
                if(e.shift){
                    this.setPage(0);
                }
                else{
                    this.previousPage();
                }
                return false;
            }
        },
        handleMouseWheel: function(e){
            if(this.annotationMode){
                return true;
            }
            
            var U = ecs.pdfviewer.utils;
            if(e.wheel > 0 && U.isAtTop() || e.wheel < 0  && U.isAtBottom()){
                if(this._wheelTimeout){
                    clearTimeout(this._wheelTimeout)
                }
                else{
                    this._wheelTimeout = setTimeout(this._wheelReset, 100);
                }
                this._wheelCounter += Math.abs(e.wheel);
                if(this._wheelCounter >= this.wheelThreshold){
                    this._wheelCounter = 0;
                    if(e.wheel > 0){
                        this.previousPage();
                    }
                    else if(e.wheel < 0){
                        this.nextPage();
                    }
                }
            }
        },
        handleClick: function(e){
            var target = $(e.target);
            var pageEl = target.hasClass('page') ? target : target.getParent('.page');
            if(this.annotationMode){
                if(pageEl && !target.getParent('.annotation')){
                    var rel = this.annotationOverlay.getCoordinates();
                    var x = (e.page.x - rel.left) / rel.width;
                    var y = (e.page.y - rel.top) / rel.height;
                    var annotation = new ecs.pdfviewer.Annotation(null, "", x - 0.01, y - 0.01, 0.02, 0.02);
                    this.addAnnotation(this.currentPageIndex, annotation);
                    var annotationElement = this.renderAnnotation(pageEl, annotation);
                    annotation.startAnnotationMode(annotationElement);
                }
                return;
            }
            if(e.alt){
                this.cycleController(e.shift ? -1 : +1);
                return false;
            }
            if(pageEl){
                this.setPage(pageEl.retrieve('pageIndex'), false);
                this.setControllerIndex(this.controllers.length - 1);
            }
        }
    }),

    Controller: new Class({
        initialize: function(imageSet, x, y, options){
            this.imageSet = imageSet;
            this.x = x;
            this.y = y;
            this.sliceLength = x * y;
            this.options = options || {'showAnnotations': true};
        },
        render: function(viewer, pageIndex){
            var blockIndex = parseInt(Math.floor(pageIndex / this.sliceLength));
            viewer.render(this.imageSet, blockIndex * this.sliceLength, this.x, this.y);
        }
    }),
    
    Annotation: new Class({
        initialize: function(pk, text, x, y, w, h){
            this.pk = pk;
            this.text = text;
            this.x = x;
            this.y = y;
            this.w = w;
            this.h = h;
        },
        attachTo: function(el, onShow){
            var a = new Element('div', {'class': 'annotation'});
            var dim = el.getSize();
            a.setStyle('top', (this.y * dim.y) + 'px');
            var overlay = new Element('div', {'class': 'overlay'});
        
            overlay.setStyles({
                left: (this.x * dim.x) + 'px', 
                top: '0px',
                width: (this.w * dim.x) + 'px',
                height: (this.h * dim.y) + 'px'
            });
            a.grab(overlay);
            var marker = new Element('div', {'class': 'marker'});
            a.grab(marker);
            el.grab(a);
            if(onShow){
                marker.addEvent('click', onShow);
                overlay.addEvent('dblclick', onShow);
            }
            return a;
        },
        startAnnotationMode: function(annotationElement){
            var overlay = annotationElement.getFirst('.overlay');
            var resizeHandle = new Element('div', {'class': 'resizeHandle'});
            var dragHandle = new Element('div', {'class': 'dragHandle'});
            overlay.grab(dragHandle);
            overlay.grab(resizeHandle);
            overlay.makeResizable({
                handle: resizeHandle,
                onComplete: this.postDragDrop.bind(this)
            });
            new Drag.Move(overlay, {
                handle: dragHandle,
                onComplete: this.postDragDrop.bind(this)
            });
        },
        endAnnotationMode: function(annotationElement){
            var overlay = annotationElement.getFirst('.overlay');
            overlay.getFirst('.resizeHandle').dispose();
            overlay.getFirst('.dragHandle').dispose();
        },
        postDragDrop: function(overlay){
            var annotationElement = overlay.getParent('.annotation');
            var pageEl = annotationElement.getParent('.page');
            var pageSize = pageEl.getSize();
            var bounds = overlay.getStyles('left', 'top', 'width', 'height');
            this.x = parseInt(bounds.left) / pageSize.x;
            this.y += parseInt(bounds.top) / pageSize.y;
            this.w = parseInt(bounds.width) / pageSize.x;
            this.h = parseInt(bounds.height) / pageSize.y;
            annotationElement.setStyle('top', (parseInt(annotationElement.getStyle('top')) + parseInt(bounds.top)) + 'px');
            overlay.setStyle('top', '0px');
        }
    }),
    
    SearchPopup: new Class({
        Implements: Events,
        initialize: function(viewer){
            this.viewer = viewer;
        },
        init: function(){
            if(this.element){
                return;
            }
            this.cover = new Element('div', {'class': 'cover'});
            this.element = new Element('div', {'class': 'searchPopup annotationDisplay popup'});
            var content = new Element('div', {'class': 'content'});
            this.input = new Element('input', {type: 'text', value: ''});
            this.input.addEvent('keypress', (function(e){
                if(e.key == 'enter'){
                    this.search();
                    return false;
                }
            }).bind(this));
            var background = new Element('div', {'class': 'background'});
            var searchLink = new Element('a', {html: 'Search'});
            searchLink.addEvent('click', (function(){
                this.search();
            }).bind(this));
            this.resultList = new Element('div', {'class': 'results'});
            this.element.grab(background);
            this.element.grab(content);
            content.grab(this.input);
            content.grab(searchLink);
            content.grab(this.resultList);
            this.escapeListener = (function(e){
                if(e.key == 'esc'){
                    this.dispose();
                    return false;
                }
            }).bind(this);
            this.cover.setStyle('display', 'none');
            this.cover.grab(this.element);
            $(document.body).appendChild(this.cover);
            new Drag.Move(this.element, {handle: background});
        },
        search: function(){
            var popup = this;
            var request = new Request.JSON({
                url: this.viewer.searchURL,
                data: $H({q: this.input.value}).toQueryString(),
                method: 'get',
                onSuccess: (function(results){
                    this.resultList.innerHTML = '';
                    results.each((function(result){
                        var el = new Element('div', {'html': '<span class="pageNumber">Seite ' + result.page_number + '</span>: ' + result.highlight});
                        el.addEvent('click', function(){
                            popup.viewer.setPage(result.page_number - 1, false);
                            popup.viewer.setControllerIndex(popup.viewer.controllers.length - 1);
                        });
                        this.resultList.grab(el);
                    }).bind(this));
                }).bind(this)
            });
            request.send();
        },
        show: function(query){
            this.init();
            if($defined(query)){
                this.input.value = query;
            }
            this.cover.setStyle('display', '');
            $(window).addEvent('keydown', this.escapeListener);
            this.input.focus();
            this.fireEvent('show');
        },
        dispose: function(){
            $(window).removeEvent(this.escapeListener);
            this.cover.setStyle('display', 'none');
            this.fireEvent('hide');
        }
    }),
    
    AnnotationEditor: new Class({
        Implements: Events,
        initialize: function(viewer, annotation){
            this.viewer = viewer;
            this.annotation = annotation || null;
        },
        init: function(){
            if(this.element){
                return;
            }
            this.cover = new Element('div', {'class': 'cover'});
            this.element = new Element('div', {'class': 'annotationDisplay popup'});
            var content = new Element('div', {'class': 'content'});
            this.textarea = new Element('textarea', {html: this.text});
            var background = new Element('div', {'class': 'background'});
            var saveLink = new Element('a', {html: 'Save'});
            var cancelLink = new Element('a', {html: 'Cancel'});
            var deleteLink = new Element('a', {html: 'Delete'});
            this.element.grab(background);
            this.element.grab(content);
            content.grab(this.textarea);
            content.grab(saveLink);
            content.grab(cancelLink);
            content.grab(deleteLink);
            saveLink.addEvent('click', this.onSave.bind(this));
            cancelLink.addEvent('click', this.onCancel.bind(this));
            deleteLink.addEvent('click', this.onDelete.bind(this));
            this.escapeListener = (function(e){
                if(e.key == 'esc'){
                    this.dispose();
                    return false;
                }
            }).bind(this);
            this.cover.setStyle('display', 'none');
            this.cover.grab(this.element);
            $(document.body).appendChild(this.cover);
            new Drag.Move(this.element, {handle: background});
        },
        dispose: function(){
            this.annotation = null;
            $(window).removeEvent(this.escapeListener);
            this.cover.setStyle('display', 'none');
            this.fireEvent('hide');
        },
        show: function(annotation, element){
            this.init();
            this.annotation = annotation;
            this.annotationElement = element;
            this.textarea.value = annotation.text;
            this.cover.setStyle('display', '');
            $(window).addEvent('keydown', this.escapeListener);
            this.textarea.focus();
            this.fireEvent('show');
        },
        onSave: function(){
            this.annotation.text = this.textarea.value;
            this.dispose();
        },
        onCancel: function(){
            this.dispose();
        },
        onDelete: function(){
            this.viewer.removeAnnotation(this.annotationElement);
            this.dispose();
        }
    })
};
