ecs.init_task_form = function() {
    var headerworkflow = $('#headerworkflow');
    var form = headerworkflow.find('form');
    var data_form = $('form.bound_to_task');

    if (data_form.length) {
        form.find('input[name=task_management-save]').removeAttr('hidden');
        form.submit(function(ev) {
            var input = form.find('input[name=task_management-post_data]');
            input.val(data_form.serialize());
        });
    }

    // The first POST closes the task, so a second one has no open task left and
    // is answered with 403 by `task_required`. Rendering the target page can
    // take a few seconds, which invites an impatient second click.
    var buttons = form.find('button[type=submit], input[type=submit]');
    var submitted = false;

    form.submit(function(ev) {
        if (submitted) {
            ev.preventDefault();
            return;
        }
        submitted = true;
        // Deferred: the clicked button must still be enabled while the browser
        // serializes the form, otherwise `task_management-action` is dropped
        // from the POST data and the task is never completed.
        window.setTimeout(function() {
            buttons.prop('disabled', true).addClass('disabled');
        }, 0);
    });

    // Going back to a still-open task must not leave the buttons dead.
    $(window).on('pageshow', function(ev) {
        if (ev.originalEvent && ev.originalEvent.persisted) {
            submitted = false;
            buttons.prop('disabled', false).removeClass('disabled');
        }
    });
};
