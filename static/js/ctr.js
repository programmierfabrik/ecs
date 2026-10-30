/*
 * Interaction for the CTIS submission path (templates/submissions/ctr/).
 *
 * The first two tab levels are driven by ecs.TabController like every other
 * submission tab; everything below that level is handled here:
 *  - third-level tabs are plain Bootstrap tabs, but their readonly textareas
 *    need ecs.textarea to re-measure once they become visible,
 *  - a chip strip picks one of a set of like items - a sponsor, a product, a
 *    member state,
 *  - the « Unterlagen » filters hide table rows client-side.
 */
ecs.ctr = {
    init: function() {
        if (!$('.ctr-tab').length)
            return;

        this.initTextAreas();
        this.initChips();
        this.initDocumentVersions();
        this.initDocumentFilters();
    },

    initTextAreas: function() {
        $('.ctr-textarea').each(function() {
            new ecs.textarea.TextArea(this);
        });

        // A textarea measures as empty while its tab is hidden, so re-measure
        // on the way in. ecs.Tab.setSelected already does this for the two
        // outer tab levels; this covers the third and the chip switch.
        $('.ctr-tab a[data-toggle="tab"]').on('shown.bs.tab', function() {
            ecs.ctr.updateTextAreas($($(this).attr('href')));
        });
    },

    updateTextAreas: function(container) {
        container.find('.ctr-textarea').each(function() {
            var textarea = $(this).data('textarea');
            if (textarea)
                textarea.updateHeight();
        });
    },

    // Chip and pane are matched by position, the way the classic centres tab
    // matches a jump-list button to its investigator form.
    initChips: function() {
        $('.ctr-chips').each(function() {
            var chips = $(this);
            var buttons = chips.children('.ctr-chip-list').find('button');
            var panes = chips.children('.ctr-chip-pane');

            buttons.click(function(ev) {
                ev.preventDefault();
                var index = buttons.index(this);

                buttons.removeClass('active');
                $(this).addClass('active');
                panes.each(function(i) {
                    $(this).toggleClass('ctr-chip-pane-active', i === index);
                });
                ecs.ctr.updateTextAreas(panes.eq(index));
            });
        });
    },

    initDocumentVersions: function() {
        $('.ctr-doc-versions-toggle').click(function(ev) {
            ev.preventDefault();
            $(this).next('.ctr-doc-versions').toggleClass('show');
        });
    },

    // An application can deliver a few hundred documents, so the list filters
    // and pages in the browser - it is all in the page already.
    initDocumentFilters: function() {
        var table = $('.ctr-doclist-table');
        if (!table.length)
            return;

        var filters = $('.ctr-doc-filter');
        // Looked up on every draw: hiding or restoring a document moves its
        // row between this table and the « Ausgeblendet » one.
        function allRows() {
            return table.find('tbody tr').not('.ctr-doclist-empty, .ctr-doclist-nomatch');
        }
        var nomatch = table.find('.ctr-doclist-nomatch');
        var pager = $('.ctr-doclist-pager');
        var perPage = parseInt(pager.data('per-page'), 10) || 20;
        var page = 0;

        function matching() {
            var selected = {};
            filters.each(function() {
                var value = $(this).val();
                if (value)
                    selected[$(this).data('filter')] = value;
            });

            return allRows().filter(function() {
                var row = $(this);
                for (var key in selected) {
                    if (String(row.data(key)) !== selected[key])
                        return false;
                }
                return true;
            });
        }

        function drawPager(pages, total) {
            pager.empty();
            if (!total)
                return;

            var count = $('<span>', {
                'class': 'text-muted mr-3',
                text: total + (total === 1 ? ' Dokument' : ' Dokumente')
            });
            pager.append(count);

            if (pages < 2)
                return;

            var group = $('<div>', {'class': 'btn-group btn-group-sm'});
            var step = function(label, target, enabled) {
                group.append($('<button>', {
                    'class': 'btn btn-outline-primary',
                    type: 'button',
                    text: label,
                    disabled: !enabled,
                    click: function(ev) {
                        ev.preventDefault();
                        page = target;
                        draw();
                    }
                }));
            };

            step('«', page - 1, page > 0);
            for (var i = 0; i < pages; i++) {
                var button = $('<button>', {
                    'class': 'btn btn-outline-primary',
                    type: 'button',
                    text: String(i + 1),
                    click: (function(target) {
                        return function(ev) {
                            ev.preventDefault();
                            page = target;
                            draw();
                        };
                    })(i)
                });
                button.toggleClass('active', i === page);
                group.append(button);
            }
            step('»', page + 1, page < pages - 1);

            pager.append(group);
        }

        function draw() {
            var visible = matching();
            var pages = Math.max(1, Math.ceil(visible.length / perPage));
            if (page > pages - 1)
                page = pages - 1;

            var rows = allRows();
            rows.prop('hidden', true);
            visible.slice(page * perPage, (page + 1) * perPage)
                   .prop('hidden', false);
            nomatch.prop('hidden', visible.length > 0 || !rows.length);
            drawPager(pages, visible.length);
        }

        // A new filter selection starts over at the first page - staying on
        // page 6 of a two-page result would look like an empty list.
        filters.change(function() {
            page = 0;
            draw();
        });

        draw();

        var list = table.closest('.ctr-doclist');
        var hiddenTable = list.find('.ctr-doclist-hidden-table');
        if (!hiddenTable.length)
            return;

        function syncHidden() {
            var count = hiddenTable.find('tbody tr[data-document-id]').length;
            list.find('.ctr-doclist-hidden-count').text(count);
            hiddenTable.find('.ctr-doclist-hidden-empty').prop('hidden', count > 0);
            table.find('.ctr-doclist-empty').prop('hidden',
                table.find('tbody tr[data-document-id]').length > 0);
        }

        // Hide and restore save at once and move the row; nothing reloads.
        list.on('click', '.ctr-doc-hide, .ctr-doc-restore', function() {
            var button = $(this);
            var row = button.closest('tr');
            var hide = button.hasClass('ctr-doc-hide');
            button.prop('disabled', true);
            $.post(list.data('hide-url'), {
                document_id: row.data('document-id'),
                hidden: hide ? '1' : '0',
                csrfmiddlewaretoken: list.data('csrf')
            }).done(function() {
                row.find('.ctr-doc-hide').prop('hidden', hide);
                row.find('.ctr-doc-restore').prop('hidden', !hide);
                row.prop('hidden', false);
                if (hide)
                    hiddenTable.find('tbody').prepend(row);
                else
                    table.find('tbody').prepend(row);
                draw();
                syncHidden();
            }).fail(function() {
                alert('Speichern fehlgeschlagen. Bitte erneut versuchen.');
            }).always(function() {
                button.prop('disabled', false);
            });
        });
    }
};
