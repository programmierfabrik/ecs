/*
 * Interaction for the CTIS submission path (templates/submissions/ctr/).
 *
 * The first two tab levels are driven by ecs.TabController like every other
 * submission tab; everything below that level is handled here:
 *  - third-level tabs are plain Bootstrap tabs, but their readonly textareas
 *    need ecs.textarea to re-measure once they become visible,
 *  - the member-state selector switches all panes of one tab at once,
 *  - the « Unterlagen » filters hide table rows client-side.
 */
ecs.ctr = {
    init: function() {
        if (!$('.ctr-tab').length)
            return;

        this.initTextAreas();
        this.initPaneSelectors();
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
        // outer tab levels; this covers the third and the pane switch.
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

    initPaneSelectors: function() {
        $('.ctr-pane-selector').each(function() {
            var selector = $(this);
            var tab = $('#' + selector.data('tab'));

            selector.find('button').click(function(ev) {
                ev.preventDefault();
                var key = String($(this).data('pane'));

                selector.find('button').removeClass('active');
                $(this).addClass('active');

                // Every subtab of this tab switches together, so the
                // selection survives moving between the third-level tabs.
                tab.find('.ctr-pane-keyed').each(function() {
                    var pane = $(this);
                    pane.toggleClass('ctr-pane-active',
                        String(pane.data('pane')) === key);
                });
                ecs.ctr.updateTextAreas(tab);
            });
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

    initDocumentFilters: function() {
        var table = $('.ctr-doclist-table');
        if (!table.length)
            return;

        var filters = $('.ctr-doc-filter');
        var rows = table.find('tbody tr').not('.ctr-doclist-empty, .ctr-doclist-nomatch');
        var nomatch = table.find('.ctr-doclist-nomatch');

        filters.change(function() {
            var selected = {};
            filters.each(function() {
                var value = $(this).val();
                if (value)
                    selected[$(this).data('filter')] = value;
            });

            var visible = 0;
            rows.each(function() {
                var row = $(this);
                var matches = true;
                for (var key in selected) {
                    if (String(row.data(key)) !== selected[key]) {
                        matches = false;
                        break;
                    }
                }
                row.prop('hidden', !matches);
                if (matches)
                    visible++;
            });

            nomatch.prop('hidden', visible > 0 || !rows.length);
        });
    }
};
