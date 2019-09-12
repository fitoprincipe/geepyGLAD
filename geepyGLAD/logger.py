# coding=utf-8
""" Logger module for a custom Logger """
import datetime
import os


class Logger(object):
    def __init__(self, name, folder=None, filetype='txt'):
        self.name = name
        self._logs = []
        self._header = None
        if not folder:
            self.path = os.getcwd()
        else:
            self.path = os.path.join(os.getcwd(), folder)
            exists = os.path.exists(self.path)
            if not exists:
                os.mkdir(self.path)

        self.filetype = filetype
        if filetype == 'txt':
            name = '{}.txt'.format(self.name)
            filename = os.path.join(self.path, name)
        else:
            raise ValueError('file type {} not allowed'.format(filetype))

        self.filename = filename

    def header(self, text):
        """ writer the header """
        exists = os.path.exists(os.path.join(self.path, self.filename))
        if not self._header and not exists:
            self._header = text
            with open(self.filename, 'a+') as f:
                f.write('{}\n\n'.format(text))

    def log(self, message):
        """ write a log into the logger """
        t = datetime.datetime.today().isoformat()
        msg = '{time} - {msg}\n'.format(time=t, msg=message)
        self._logs.append(msg)
        with open(self.filename, 'a+') as f:
            try:
                f.write(msg)
            except UnicodeEncodeError:
                f.write(msg.encode('utf-8').decode())
            except Exception as e:
                f.write(str(e))

    def text(self):
        """ get the log message as a string """
        body = '\n'.join(self._logs)
        if self._header:
            body = "{}\n\n{}".format(self._header, body)
        return body
