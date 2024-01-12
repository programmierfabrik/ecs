from __future__ import unicode_literals

import re

from django.db import migrations

from ecs.docstash.models import DocStash


def migrate_employees(apps, schema_editor):
    for doc in DocStash.objects.filter(group='ecs.core.views.submissions.create_submission_form'):
        if not doc.POST:
            continue

        # 1: parse query string
        parsed_value = doc.POST
        parsed_value._mutable = True
        to_remove = [
            'investigatoremployee-TOTAL_FORMS', 'investigatoremployee-INITIAL_FORMS',
            'investigatoremployee-MIN_NUM_FORMS', 'investigatoremployee-MAX_NUM_FORMS'
        ]

        for key in to_remove:
            try:
                del parsed_value[key]
            except KeyError:
                pass

        # 2: add counter/index for each investigator
        investigator_indicies = set()
        for k, v in parsed_value.items():
            result = re.search(r"investigator-(\d*)", k)
            if result and result.group(1) != '':
                investigator_indicies.add(result.group(1))

        investigator_indicies_counter = dict.fromkeys(investigator_indicies, 0)

        # 3: find investigator_index
        employee_indicies = {}
        for k, v in list(parsed_value.items()):
            result = re.search(r"investigatoremployee-(\d+)-investigator_index", k)
            if result:
                pop = parsed_value.pop(k)
                employee_indicies[int(result.group(1))] = pop[0] if pop[0] != '' else '0'

        # 4: for each investigator_index update all the investigatoremployee and use the correct investigator
        for k, v in sorted(employee_indicies.items()):
            employee_index = str(investigator_indicies_counter[v])
            for field in ['sex', 'title', 'suffix_title', 'firstname', 'surname', 'organisation']:
                # investigator-0-employee-0-firstname
                try:
                    parsed_value['investigator-' + str(v) + '-employee-' + employee_index + '-' + field] = (
                        parsed_value.pop('investigatoremployee-' + str(k) + '-' + field)[0]
                    )
                except KeyError:
                    pass

            investigator_indicies_counter[v] += 1

        # set metadata for each investigator-x-employee
        for k, v in sorted(investigator_indicies_counter.items()):
            employee_base = 'investigator-' + str(k) + '-employee-'
            parsed_value[employee_base + 'MAX_NUM_FORMS'] = 0
            parsed_value[employee_base + 'MIN_NUM_FORMS'] = 0

            parsed_value[employee_base + 'INITIAL_FORMS'] = v
            parsed_value[employee_base + 'TOTAL_FORMS'] = v

        doc.POST = parsed_value
        doc.save()


class Migration(migrations.Migration):

    dependencies = [
        ('docstash', '0011_fix_categorization'),
        ('docstash', '0012_remove_checklist_docstashes'),
    ]

    operations = [
        migrations.RunPython(migrate_employees),
    ]
