from django.db import migrations


def backfill_vote_submission(apps, schema_editor):
    Vote = apps.get_model('votes', 'Vote')
    votes = list(
        Vote.objects.filter(submission__isnull=True, submission_form__isnull=False)
        .select_related('submission_form')
    )
    for vote in votes:
        vote.submission_id = vote.submission_form.submission_id
    Vote.objects.bulk_update(votes, ['submission_id'], batch_size=1000)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('votes', '0010_vote_ctr_submission_form_vote_submission_and_more'),
    ]

    operations = [
        migrations.RunPython(backfill_vote_submission, noop),
    ]
