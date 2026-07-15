import urllib.request, urllib.parse, urllib.error
import urllib.request, urllib.error, urllib.parse
import traceback
import logging
import sys
import hashlib
import uuid
import base64
import json
import requests

from tempfile import TemporaryFile

from django.conf import settings
from django.http import HttpResponse
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from django.shortcuts import render, redirect
from django.utils.translation import gettext as _

from ecs.utils import forceauth

from ecs.users.utils import sudo, user_group_required
from ecs.documents.models import Document
from ecs.utils.pdfutils import pdf_barcodestamp
from ecs.tasks.models import Task

from ecs.signature.utils import SigningData, with_sign_data, get_pdfas_url


logger = logging.getLogger(__name__)


def _get_tasks(user):
    return Task.objects.for_user(user).filter(closed_at=None, assigned_to=user)

def _store_sign_data(sign_data, force_mock=False):
    sign_data = SigningData(sign_data)

    if sign_data['document_barcodestamp']:
        with TemporaryFile() as tmp_in:
            tmp_in.write(sign_data['pdf_data'])
            tmp_in.seek(0)
            stamped = pdf_barcodestamp(tmp_in, sign_data['document_uuid'])
            sign_data['pdf_data'] = stamped.read()

    sign_data['origdigest'] = hashlib.sha256(sign_data['pdf_data']).hexdigest()
    sign_data.store(minutes=5)
    return sign_data


@user_group_required("EC-Signing")
def init_batch_sign(request, task, data_func):
    if request.user.email.startswith('signing_mock') or settings.PDFAS_SERVICE == 'mock:':
        sign_data = data_func(request, task)
        rval = sign(request, sign_data)
        _get_tasks(request.user).get(pk=task.pk).done(choice=True)
        return rval
    tasks = [task.pk]
    tasks += list(_get_tasks(request.user).filter(task_type__workflow_node__uid=task.task_type.workflow_node.uid).exclude(pk=task.pk).order_by('created_at').values_list('pk', flat=True))
    sign_session = SigningData(tasks=tasks, data_func=data_func, selected_tasks=[])
    sign_session.store(hours=1)
    return redirect('signature.batch_sign', sign_session_id=sign_session.id)


@user_group_required("EC-Signing")
@with_sign_data(data=False, session=True)
def batch_sign(request, index=0):
    tasks = request.sign_session['tasks']
    if not tasks:
        return redirect('dashboard')

    if index >= len(tasks):
        index = len(tasks) - 1
    if index < 0:
        index = 0

    task_pk = tasks[index]
    task = _get_tasks(request.user).get(pk=task_pk)
    data = request.sign_session['data_func'](request, task)
    data['task_pk'] = task_pk
    data['sign_session_id'] = request.sign_session.id
    sign_data = _store_sign_data(data)

    if request.user.email.startswith('signing_fail'):
        return sign_error(request, pdf_id=sign_data.id, error='forced failure', cause='requested force_fail, so we failed')

    selected_tasks = request.sign_session.get('selected_tasks', [])

    return render(request, 'signature/batch.html', {
        'pdf_id': sign_data.id,
        'index': index,
        'task_count': len(tasks),
        'is_selected': task_pk in selected_tasks,
        'has_prev': index > 0,
        'has_next': index < len(tasks) - 1,
        'selected_count': len(selected_tasks),
    })


@user_group_required("EC-Signing")
@with_sign_data(session=True)
def batch_action(request, action=None):
    if request.sign_data:
        request.sign_data.delete()

    index = int(request.GET.get('index', 0))
    tasks = request.sign_session['tasks']

    if action in ['skip', 'pushback']:
        task_pk = tasks[index]
        if task_pk in request.sign_session.get('selected_tasks', []):
            return redirect('signature.batch_sign', sign_session_id=request.sign_session.id, index=index)
        task_pk = request.sign_session.pop_listitem('tasks', index)
        task = _get_tasks(request.user).get(pk=task_pk)
        if action == 'pushback' and task:
            task.done(choice=False)
            with sudo():
                previous_task = task.trail.closed().exclude(pk=task.pk).order_by('-closed_at')[0]
                new_task = previous_task.reopen()
                new_task.review_for = previous_task.review_for
                new_task.save()
    elif action == 'cancel':
        request.sign_session.delete()
        return redirect('dashboard')
    elif action == 'select':
        task_pk = tasks[index]
        if task_pk not in request.sign_session.get('selected_tasks', []):
            request.sign_session.setdefault('selected_tasks', []).append(task_pk)
            request.sign_session.store()
    elif action == 'deselect':
        task_pk = tasks[index]
        if task_pk in request.sign_session.get('selected_tasks', []):
            request.sign_session['selected_tasks'].remove(task_pk)
            request.sign_session.store()
    
    url = reverse('signature.batch_sign', kwargs={'sign_session_id': request.sign_session.id, 'index': index})
    if action == 'next':
        url = reverse('signature.batch_sign', kwargs={'sign_session_id': request.sign_session.id, 'index': index + 1})
    elif action == 'prev':
        url = reverse('signature.batch_sign', kwargs={'sign_session_id': request.sign_session.id, 'index': index - 1})
    elif action == 'cancel':
        url = reverse('dashboard')
    
    return redirect(url)


@user_group_required("EC-Signing")
@with_sign_data(data=False, session=True)
def bulk_sign(request):
    selected_tasks = request.sign_session.get('selected_tasks', [])
    if not selected_tasks:
        return redirect('signature.batch_sign', sign_session_id=request.sign_session.id)

    if request.user.email.startswith('signing_mock') or settings.PDFAS_SERVICE == 'mock:':
        for task_pk in selected_tasks:
            task = _get_tasks(request.user).get(pk=task_pk)
            data = request.sign_session['data_func'](request, task)
            data['task_pk'] = task_pk
            sign_data = _store_sign_data(data)
            with transaction.atomic():
                _receive_document(request, sign_data, request.sign_session, sign_data['pdf_data'])
        # Bulk-signing concludes the whole batch, even if some tasks were left unselected.
        request.sign_session.delete()
        return redirect('dashboard')

    input_data = []
    pdf_metadata = {}
    for task_pk in selected_tasks:
        task = _get_tasks(request.user).get(pk=task_pk)
        data = request.sign_session['data_func'](request, task)
        data['task_pk'] = task_pk
        sign_data = _store_sign_data(data)
        filename = f"{sign_data.id}.pdf"
        pdf_metadata[filename] = sign_data.id
        input_data.append({
            "fileName": filename,
            "inputData": base64.b64encode(sign_data['pdf_data']).decode('utf-8'),
            "profile": "SIGNATURBLOCK_DE",
        })
    
    request.sign_session['bulk_metadata'] = pdf_metadata
    request.sign_session.store()

    invoke_url = request.build_absolute_uri(reverse('signature.bulk_receive', kwargs={'sign_session_id': request.sign_session.id}))

    # Field names deviate from the published PdfasSignMultipleRequest schema (which uses
    # "input" and "invokeUrl" only) - this appliance's actual deployment only recognizes
    # "documents", and needs invoke-url in both casings to redirect back after signing.
    payload = {
        "requestID": str(uuid.uuid4()),
        "connector": request.user.profile.signing_connector,
        "invokeUrl": invoke_url,
        "invoke-url": invoke_url,
        "documents": input_data,
    }

    url = f"{settings.PDFAS_SERVICE}api/v2/sign/multiple"
    try:
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        redirect_url = response.json()['redirectUrl']
        return redirect(redirect_url)
    except requests.exceptions.HTTPError as e:
        logger.warn('Bulk Signing Error', exc_info=sys.exc_info())
        error_msg = str(e)
        try:
            error_msg += f" - Response: {e.response.text}"
        except:
            pass
        return HttpResponse(_("Bulk signing failed: {error}").format(error=error_msg), status=500)
    except Exception as e:
        logger.warn('Bulk Signing Error', exc_info=sys.exc_info())
        return HttpResponse(_("Bulk signing failed: {error}").format(error=str(e)), status=500)

@user_group_required("EC-Signing")
@csrf_exempt
@with_sign_data(data=False, session=True)
def bulk_receive(request):
    ''' accessed by pdf-as after bulk signing completes; this appliance calls back with
    pdfurl/pdflength (same convention as the single-document flow) rather than a token,
    so the token branch below is a no-op here but kept for other pdf-as-web deployments '''
    token = request.GET.get('token') or request.POST.get('token')
    if not token:
        # Check all possible names
        for alt_name in ['pdfas-token', 'signedPDFToken', 'xml-token']:
            token = request.GET.get(alt_name) or request.POST.get(alt_name)
            if token:
                break
    
    if not token and request.content_type == 'application/json':
        try:
            data = json.loads(request.body)
            token = data.get('token')
        except:
            pass

    if not token and 'pdfurl' in request.GET:
        # pdf-as invokes this URL once per signed document in the batch, so we can't
        # finish the batch on the first call - each arrival is removed from bulk_metadata
        # and the session is only torn down once every selected document has been received.
        pdfurl = urllib.parse.unquote(request.GET['pdfurl'])
        pdflength = int(request.GET.get('pdflength', 0))

        try:
            if not pdfurl.startswith(settings.PDFAS_SERVICE):
                if pdfurl.startswith('/'):
                    base_url = settings.PDFAS_SERVICE.rstrip('/')
                    pdfurl = base_url + pdfurl
                else:
                    raise RuntimeError(f"pdfurl does not start with settings.PDFAS_SERVICE: {pdfurl}")

            sock_pdfas = urllib.request.urlopen(pdfurl)
            pdf_data = sock_pdfas.read(pdflength) if pdflength > 0 else sock_pdfas.read()

            # pdfurl doesn't reliably embed the filename, so with only one document left
            # to receive we take it unconditionally rather than requiring a name match.
            bulk_metadata = request.sign_session.get('bulk_metadata', {})
            matched_filename = None
            if len(bulk_metadata) == 1:
                matched_filename = list(bulk_metadata.keys())[0]
            else:
                for filename in bulk_metadata:
                    if filename in pdfurl:
                        matched_filename = filename
                        break

            if matched_filename:
                pdf_id = bulk_metadata.pop(matched_filename)
                sign_data_to_process = SigningData.retrieve(pdf_id)
                with transaction.atomic():
                    _receive_document(request, sign_data_to_process, request.sign_session, pdf_data)
                    sign_data_to_process.delete()

                if bulk_metadata:
                    request.sign_session['bulk_metadata'] = bulk_metadata
                    request.sign_session.store()
                    return HttpResponse(_("{count} document(s) still pending in this batch.").format(count=len(bulk_metadata)))

                request.sign_session.delete()
                return redirect('dashboard')
            else:
                return HttpResponse(_("Could not match pdfurl to any document in session. Metadata keys: {keys}, pdfurl: {pdfurl}").format(
                    keys=", ".join(bulk_metadata.keys()), pdfurl=pdfurl
                ), status=400)
        except Exception as e:
            logger.warn('Bulk Receive Fallback Error', exc_info=sys.exc_info())
            return HttpResponse(_("Bulk receive fallback failed: {error}").format(error=str(e)), status=500)

    if not token:
        get_keys = list(request.GET.keys())
        post_keys = list(request.POST.keys())
        msg = _("Missing token. GET keys: {get_keys}, POST keys: {post_keys}").format(
            get_keys=", ".join(get_keys), post_keys=", ".join(post_keys)
        )
        return HttpResponse(msg, status=400)
    
    url = f"{settings.PDFAS_SERVICE}api/v2/sign/multiple/get-result"
    try:
        response = requests.post(url, json={"token": token}, timeout=30)
        response.raise_for_status()
        result = response.json()
        
        if result.get('error'):
            return HttpResponse(_("Bulk signing failed at provider: {error}").format(error=result['error']), status=400)

        bulk_metadata = request.sign_session.get('bulk_metadata', {})
        outputs = result.get('output', []) or result.get('documents', [])
        
        processed_count = 0
        with transaction.atomic():
            for output in outputs:
                filename = output.get('fileName') or output.get('filename')
                pdf_id = bulk_metadata.get(filename)
                
                # Try flexible matching if exact match fails
                if not pdf_id and filename:
                    for k, v in bulk_metadata.items():
                        if k in filename or filename in k:
                            pdf_id = v
                            break
                
                if pdf_id:
                    sign_data = SigningData.retrieve(pdf_id)
                    if sign_data:
                        pdf_data = base64.b64decode(output.get('outputData') or output.get('data', ''))
                        _receive_document(request, sign_data, request.sign_session, pdf_data)
                        sign_data.delete()
                        processed_count += 1
        
        logger.info(f"Bulk receive processed {processed_count} of {len(outputs)} documents.")

        request.sign_session.delete()
        return redirect('dashboard')
    except requests.exceptions.HTTPError as e:
        logger.warn('Bulk Receive Error', exc_info=sys.exc_info())
        error_msg = str(e)
        try:
            error_msg += f" - Response: {e.response.text}"
        except:
            pass
        return HttpResponse(_("Bulk receive failed: {error}").format(error=error_msg), status=500)
    except Exception as e:
        logger.warn('Bulk Receive Error', exc_info=sys.exc_info())
        return HttpResponse(_("Bulk receive failed: {error}").format(error=str(e)), status=500)

@user_group_required("EC-Signing")
def sign(request, sign_data, force_mock=False, force_fail=False):
    fail = force_fail or request.user.email.startswith('signing_fail')
    mock = force_mock or request.user.email.startswith('signing_mock') or settings.PDFAS_SERVICE == 'mock:'

    sign_data = _store_sign_data(sign_data)

    if fail:
        return sign_error(request, pdf_id=sign_data.id, error='forced failure', cause='requested force_fail, so we failed')
    elif mock:
        return sign_receive(request, pdf_id=sign_data.id, mock=mock)

    url = get_pdfas_url(request, sign_data)
    return redirect(url)

# FIXME allow only from same host as server
@csrf_exempt
@forceauth.exempt
@with_sign_data()
def sign_send(request):
    return HttpResponse(request.sign_data["pdf_data"], content_type='application/pdf')

@user_group_required("EC-Signing")
@with_sign_data()
def sign_preview(request):
    return HttpResponse(request.sign_data["html_preview"])

def _receive_document(request, sign_data, sign_session, pdf_data):
    document = Document.objects.create_from_buffer(pdf_data,
        uuid=uuid.UUID(sign_data["document_uuid"]),
        stamp_on_download=False, doctype=sign_data['document_type'],
        original_file_name=sign_data["document_filename"],
        version=sign_data["document_version"]
    )
    parent_model = sign_data.get('parent_type')
    if parent_model:
        document.parent_object = parent_model.objects.get(pk=sign_data['parent_pk'])
        document.save()

    # called unconditionally, because the function can have side effects
    sign_data['success_func'](request, document=document)

    if sign_session:
        task_pk = sign_data.get('task_pk')
        if task_pk:
            if task_pk in sign_session['tasks']:
                sign_session['tasks'].remove(task_pk)
            if 'selected_tasks' in sign_session and task_pk in sign_session['selected_tasks']:
                sign_session['selected_tasks'].remove(task_pk)
            sign_session.store()
            _get_tasks(request.user).get(pk=task_pk).done(choice=True)
        else:
            task_pk = sign_session.pop_listitem('tasks', 0)
            _get_tasks(request.user).get(pk=task_pk).done(choice=True)

    return document

@user_group_required("EC-Signing")
@csrf_exempt
@with_sign_data()
def sign_receive(request, mock=False):
    ''' accessed by pdf-as when the pdf has been successfully signed '''
    pdfurl_str = None
    try:
        with transaction.atomic():
            if mock:
                pdfurl_str = "mock:"
                pdf_data = request.sign_data['pdf_data']
            else:
                pdfurl_str = urllib.parse.unquote(request.GET['pdfurl'])
                if not pdfurl_str.startswith(settings.PDFAS_SERVICE):
                    raise RuntimeError("pdfurl does not start with settings.PDFAS_SERVICE: {0} != {1}".format(settings.PDFAS_SERVICE, pdfurl_str))
                sock_pdfas = urllib.request.urlopen(pdfurl_str)
                # TODO: verify "ValueCheckCode" and "CertificateCheckCode" in http header
                # ValueCheckCode= 0 => ok, 1=> err, CertificateCheckCode=0 => OK, 2-5 Verify Error, 99 Other verify Error, raise exception if verify fails
                pdf_data = sock_pdfas.read(int(request.GET['pdflength']))

            _receive_document(request, request.sign_data, request.sign_session, pdf_data)

    except Exception as e:
        logger.warn('Signing Error', exc_info=sys.exc_info())
        return sign_error(request, pdf_id=request.sign_data.id, error=repr(e)+ " url: {0}".format(pdfurl_str), cause=traceback.format_exc())

    else:
        request.sign_data.delete()
        url = reverse('dashboard')
        if request.sign_session:
            if request.sign_session['tasks']:
                url = reverse('signature.batch_sign', kwargs={'sign_session_id': request.sign_session.id})
        return redirect(url)


@user_group_required("EC-Signing")
@csrf_exempt
@with_sign_data(data=False)
def sign_error(request, error=None, cause=None):
    ''' accessed by pdf-as and our own code when an error occured '''
    error = error or urllib.parse.unquote_plus(request.GET.get('error', ''))
    cause = cause or urllib.parse.unquote_plus(request.GET.get('cause', ''))

    if request.sign_session is None:
        return HttpResponse(_('signing failed\n\nerror: {0}\ncause:\n{1}').format(error, cause), content_type='text/plain')

    pdf_id = request.sign_data.id if request.sign_data else None
    if not pdf_id and request.sign_session and request.sign_session.get('bulk_metadata'):
        pdf_id = list(request.sign_session['bulk_metadata'].values())[0]

    return render(request, 'signature/error.html', {
        'pdf_id': pdf_id,
        'error': error,
        'cause': cause,
    })
