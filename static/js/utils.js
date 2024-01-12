ecs.setupFormFieldHelpers = function(context){
    context = $(context || document.body);

    $(context)
        .find('.DateField > input, .DateTimeField > input[name$=_0]')
        .datepicker({
            format: 'dd.mm.yyyy',
            autoclose: true,
            weekStart: 1
        });

    context.find('.CharField textarea').each(function() {
        new ecs.textarea.TextArea(this);
    });

    context.find('li,th.label').each(function() {
        var field = $(this);
        var input = null;
        if (field.is('th')) {
            var index = field.index();
            var row = field.parents('table').find('tbody > tr');
            if (row.length)
                input = $(row.find('td').get(index)).find('input[type=text]');
        } else {
            input = field.find('input[type=text]');
        }
        if (input && input.length) {
            var maxlength = input.prop('maxlength');
            if (maxlength && maxlength > 0) {
                var ml = 1 + parseInt(maxlength / 10);
                if (ml == 3)
                    ml = 4;
                else if (ml >= 5)
                    ml = 6;
                field.addClass('max' + 10*ml);
            }
        }
    });
};

ecs.InvestigatorFormset = function(container, readonly) {
    this.container = container;
    this.readonly = readonly;
    var _this = this;
    this.employeeTrTemplate = container.find('.investigatoremployee .form.template').first().clone(true, true);

    this.inline_formset = new ecs.InlineFormSet(this.container, {
        prefix: 'investigator',
        formSelector: '.investigator',
        addButton: false,
        removeButton: false,
        onFormAdded: (function(form, index) {
            form.find('.investigatoremployee tbody').html('');
            // Set the new id with the proper index
            form.attr("id", "investigator" + index);

            var investigatorEmployee = form.find(".investigatoremployee").first();
            investigatorEmployee.removeClass(function (index, className) {
                // Split the class names into an array
                var classNames = className.split(' ');

                // Filter the array to keep only classes starting with "investigatoremployee_formset"
                var filteredClasses = classNames.filter(function (name) {
                    return name.indexOf("investigatoremployee_formset") == 0;
                });

                // Join the remaining classes and return them
                return filteredClasses.join(' ');
            });
            investigatorEmployee.addClass("investigatoremployee_formset" + index);

            investigatorEmployee.find('tbody').append(_this.employeeTrTemplate.clone(true, true));
            form.find('input, select, textarea, label')
                .not(form.find('.inline_formset input, .inline_formset select, .inline_formset textarea, .inline_formset label'))
                .each(function () {
                    var el = $(this);

                    ['id', 'name', 'for'].forEach(function (f) {
                        var val = el.attr(f);
                        if (val) {
                            el.attr(f, val.replace(/-\d-/, "-" + index + "-"));
                        }
                    });
                });
            form.find('#id_investigator-' + index + '-employee-TOTAL_FORMS').val(0)
            form.find('#id_investigator-' + index + '-employee-INITIAL_FORMS').val(0)

            _this.initEmployee(form);
        }).bind(this),
        onFormRemoved: (function(form, index) {
            this.generateJumpList();

            var form_count = this.inline_formset.forms.length;
            this.show(form_count-1 <= index ? form_count - 1 : index);
        }).bind(this),
        onFormIndexChanged: function(form, index) {
            form.find('input[name$=-investigator_index]').val(index);
        }
    });

    if (this.inline_formset.forms.length > 0) {
        this.generateJumpList();
        this.show(0);
    }

    if (this.readonly)
        return;

    /*** read/write ***/

    // go over all formsets
    this.container.find(".investigator").each(function () {
        _this.initEmployee($(this));
    });
};
ecs.InvestigatorFormset.prototype = {
    show: function(index) {
        $('.investigator_list li button:not(.remove)').each(function(i) {
            $(this).toggleClass('active', i == index);
        });

        this.inline_formset.forms.forEach(function(f, i){
            f.toggle(i == index);
        });

        this.container.find('textarea:visible').each(function() {
            var textarea = $(this).data('textarea');
            if (textarea)
                textarea.updateHeight();
        });
    },
    add: function() {
        this.inline_formset.add(this.container);
        var index = this.inline_formset.forms.length - 1;
        this.inline_formset.forms[index].find('.has-danger').removeClass('has-danger');
        this.generateJumpList();
        this.show(index);
    },
    generateJumpList: function() {
        var ul = $('.investigator_list');
        ul.html('');

        this.inline_formset.forms.forEach(function(form, i) {
            var li = $('<li>', { 'class': 'btn-group mr-2 mb-2'});
            li.toggleClass('readonly', this.readonly);
            li.toggleClass('errors', !!form.find('.has-danger').length);

            var a = $('<button>', {
                'class': 'btn text-truncate',
                click: (function(ev){
                    ev.preventDefault();
                    this.show(i);
                }).bind(this),
                css: {'max-width': '20rem'}
            });
            li.append(a);

            if (form.is('.closed'))
                a.addClass('btn-secondary');
            else
                a.addClass('btn-outline-primary');

            var org = form.find('textarea[name$="-organisation"]');
            org.change(function() {
                a.text(org.val().trim() || ('Zentrum ' + (i + 1)));
            });
            org.change();

            if (!this.readonly && this.inline_formset.forms.length > 1) {
                var removeLink = $('<button>', {
                    'class': 'btn btn-outline-danger remove',
                    html: '<span class="fa fa-ban"></span>',
                    click: (function(ev) {
                        ev.preventDefault();
                        this.inline_formset.remove(i);
                    }).bind(this)
                });
                li.append(removeLink);
            }

            ul.append(li);
        }, this);

        if (!this.readonly) {
            var li = $('<li>', {
                'class': 'btn btn-outline-success mb-1',
                html: '<span class="fa fa-plus-circle"></span>',
                click: (function(ev) {
                    ev.preventDefault();
                    this.add();
                }).bind(this)
            });
            ul.append(li);
        }
    },
    initEmployee: function (container) {
        var investigatorEmployee = container.find(".investigatoremployee").first();
        var parentParentId = investigatorEmployee.parent().parent().attr("id");
        var investiagtorNumber = parentParentId.charAt(parentParentId.length - 1);

        var classList = investigatorEmployee.attr("class").split(/\s+/);
        // We know that this is the table we are searching for. now get the correct class, so we have our index.
        for (var i = 0; i < classList.length; i++) {
            var clazz = classList[i];
            if (clazz.startsWith('investigatoremployee_formset')) {
                var inlineFormSet = new ecs.InlineFormSet('.' + clazz, {
                    prefix: 'investigator-' + investiagtorNumber + '-employee',
                    indexRegex: /-(__prefix__|employee-\d)-/,
                    computeIndexReplaceValue: function(options) {
                        var index = options.index;
                        var val = options.val;

                        if (val.includes('__prefix__')) {
                            return '-' + index + '-';
                        } else {
                            return '-employee-' + index + '-';
                        }
                    }
                });
            }
        }
    }
};

ecs.setupDocumentUploadForms = function(){
    var form = $('.document_upload form');
    var upload_button = form.find('input[type="submit"]');
    var progress = form.find('progress');
    var warning = form.find('.warning');

    ecs.setupFormFieldHelpers(form);

    upload_button.click(function(ev) {
        ev.preventDefault();

        upload_button.hide();
        warning.show();
        progress.show();

        var xhr = new XMLHttpRequest();

        xhr.upload.addEventListener('progress', function(ev){
            if (ev.lengthComputable) {
                progress.attr('value', ev.loaded);
                progress.attr('max', ev.total);
                progress.html('' + Math.round(ev.loaded * 100 / ev.total) + '%');
            } else {
                progress.attr('value', null);
                progress.attr('max', null);
            }
        }, false);

        xhr.addEventListener('load', function(ev){
            $('.upload_container').html(xhr.responseText);
        }, false);

        ['abort', 'error'].forEach(function(type) {
            xhr.addEventListener(type, function(ev){
                warning.hide();
                progress.hide();
                upload_button.addClass('error').show();
            }, false);
        });

        if (ecs.mainForm) {
            ecs.mainForm.toggleAutosave(false);
            xhr.addEventListener('loadend', function(ev){
                ecs.mainForm.toggleAutosave(true);
            }, false);
        }

        xhr.open('POST', form.attr('action'));
        xhr.send(new FormData(form[0]));
    });

    var file_field = $('#id_document-file');
    var name_field = $('#id_document-name');
    file_field.change(function() {
        var name = file_field.val().split('\\').pop();

        var dot_offset = name.lastIndexOf('.');
        if (dot_offset >= 0)
            name = name.substring(0, dot_offset);

        name_field.val(name);
    });

    $('.doclist a.replace_document').click(function(ev) {
        ev.preventDefault();
        var link = $(this);

        form.find('input[name="document-replaces_document"]')
            .val($(this).data('documentId'));

        $('#replaced_document_name')
            .html(link.siblings('.document_display_name').html())
            .parent().show();

        form.find('select[name="document-doctype"]')
            .val(link.data('documentType'))
            .attr('readonly', true);
    });

    $('#tabs-11 a.new_document').click(function(ev) {
        ev.preventDefault();

        form.find('input[name="document-replaces_document"]')
            .val(null);

        $('#replaced_document_name')
            .html(null)
            .parent('li').hide();

        form.find('select[name="document-doctype"]')
            .val(null)
            .attr('readonly', false);
    });

    $('.doclist a.delete_document').click(function(ev) {
        ev.preventDefault();
        $('.upload_container').load($(this).attr('href'));
    });
};

ecs.setupForms = function(){
    var setup = {};
    if ($('.tab_headers').length) {
        var tabController = new ecs.TabController('.tab_header_groups a');
        var mainForm = $('.form_main');
        var readonly = !mainForm.is('form');

        if (mainForm.length) {
            var form = ecs.mainForm = new ecs.TabbedForm(mainForm,
                tabController, readonly ? null : 120);
            setup.mainForm = form;
        }

        var ifs = $('#tabs-12');
        if (ifs.length)
            new ecs.InvestigatorFormset(ifs, readonly);

        setup.tabController = tabController;
    }

    ecs.setupFormFieldHelpers();

    return setup;
};

ecs.setupWidgets = function(){
    $('div[data-widget-url]').each(function() {
        var widget = $(this);
        var options = {
            url: widget.data('widgetUrl'),
            reload_interval: parseInt(widget.data('widgetReloadInterval')) * 1000 || null,
        };
        new ecs.Widget(this, options);
    });
};

ecs.FormFieldController = function(options) {
    this.fields = $(options.fields);

    if (options.disable)
        this.setDisabled(true);

    this.auto = options.auto || function() {
        if (this.sources.length)
            this.fields.prop('checked', this.sources.is(':checked'));
        this.fields.change();
    };

    this.sources = $(options.sources);
    this.sources.change((function(ev) {
        this.auto.apply(this);
    }).bind(this));
    if (options.sourceFieldClass) {
        this.sources.each(function() {
            $(this).closest('.form-check').addClass(options.sourceFieldClass);
        });
    }

    this.toggleTab = options.toggleTab;
    if (this.toggleTab) {
        this.fields.change(this.onFieldValueChange.bind(this));
        this.onFieldValueChange(null);
    }

    this.auto.apply(this);
};
ecs.FormFieldController.prototype = {
    requireField: function(f, enable) {
        var li = f.parents('li');
        li.toggleClass('required', enable);
        if (!enable)
            li.find('label .errorlist').hide();
    },
    onFieldValueChange: function(ev) {
        var enable = this.getValues().some(function(x) { return !!x;});
        this.toggleTab.tab.setDisabled(!enable);
        if (this.toggleTab.requiredFields)
            this.requireField($(this.toggleTab.requiredFields), enable);
    },
    setDisabled: function(disable) {
        this.fields.prop('disabled', disable);
    },
    getValues: function() {
        return this.fields.map((function(i, el) {
            return this.getValue(el);
        }).bind(this)).get();
    },
    getValue: function(field) {
        field = $(field);
        if (field.attr('type') == 'checkbox')
            return field.is(':checked');
        return field.val();
    }
};

ecs.setupMessagePopup = function(container) {
    function show_selected_receiver() {
        var checked_input = container.find('input[name="receiver_type"]:checked');
        if (!checked_input.length)
            return;
        var value = checked_input.val();

        ['ec', 'involved', 'person'].forEach(function(f) {
            var el = container.find('#id_receiver_' + f);
            el.prop('disabled', f != value);
            el.find('.errors').toggle(f == value);
        });
    }

    show_selected_receiver();

    container.find('input[name="receiver_type"]').change(function(ev) {
        show_selected_receiver();
    });
};

ecs.setupSubmitLinks = function(selector){
    $(selector).click(function(ev) {
        ev.preventDefault();
        $(this).parent('form').submit();
    });
};

ecs.stopPageLoad = function() {
    if (typeof(window.stop) !== 'undefined') {
        window.stop();
    } else {
        try { document.execCommand('Stop'); } catch(e){};
    }
};

ecs.openSnackbar = function (status, message, duration) {
    var snackbar = document.createElement("div");
    snackbar.classList.add("slick-snackbar", "show", status);

    var closeButton = document.createElement("button");
    closeButton.classList.add("fa", "fa-close", "close");
    closeButton.onclick = function () {
        snackbar.remove();
    };

    var iconClass = "";
    switch (status) {
        case "success":
            iconClass = "fa-check-circle";
            break;
        case "error":
            iconClass = "fa-exclamation-circle";
            break;
        case "warning":
            iconClass = "fa-exclamation-triangle";
            break;
    }

    var icon = document.createElement("span");
    icon.classList.add("fa", "fa-2x", iconClass, "mr-2");

    var messageElement = document.createElement("div");
    messageElement.classList.add("mr-3", "ml-2");
    messageElement.style.whiteSpace = "pre-line";
    messageElement.textContent = message;

    snackbar.append(closeButton, icon, messageElement);
    document.body.appendChild(snackbar);

    setTimeout(function () {
        snackbar.classList.remove("show");
        snackbar.classList.add("remove");

        setTimeout(function () {
            snackbar.remove();
        }, 500);
    }, duration);
};
