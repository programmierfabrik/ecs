#!/usr/bin/env python3
import getopt
import io
import os
import sys
import mimetypes

from weasyprint import HTML, default_url_fetcher

static_root = None


def _url_fetcher(url):
    if url.startswith('static:'):
        path = os.path.abspath(os.path.join(static_root, url[len('static:'):]))
        if not path.startswith(static_root):
            raise ValueError('static: URI points outside of static directory!')
        with open(path, 'rb') as f:
            data = f.read()
        return {'string': data, 'mime_type': mimetypes.guess_type(path)[0]}

    return default_url_fetcher(url)


def usage():
    print('usage: {} -s static_root'.format(sys.argv[0]), file=sys.stderr)
    sys.exit(1)


def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], 's:')
    except getopt.GetoptError as e:
        print(e)
        usage()

    for opt, arg in opts:
        if opt == '-s':
            global static_root
            static_root = arg
        else:
            usage()

    if not static_root or args:
        usage()

    html = sys.stdin.read()

    html = html.encode('utf-8')
    HTML(string=html, url_fetcher=_url_fetcher).write_pdf(
        sys.stdout.buffer)


if __name__ == '__main__':
    main()
