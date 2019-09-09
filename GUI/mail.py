import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
DEFAULT_EMAIL = ""
DEFAULT_EMAIL_PASSWORD = ""

class SendMail:
    def __init__(self, to, host, port, login, password, subject, message):
        self.login, self.password = login, password
        self.host, self.port = host, port
        self.server = ServerManager()
        self.msg = MailManager(login, to, subject, message)

    def connect_and_send(self):
        connection_status = self.server.connect(self.host, self.port)
        if connection_status:
            login_status = self.server.login(self.login, self.password)
            if login_status:
                self.server.send_message(self.msg.msg)
            self.server.close()


class MailManager:
    def __init__(self, from_addr, to_addr, subject, message):
        self.from_addr = from_addr
        self.to_addr = to_addr
        self.subject = subject
        self.message = message
        self.msg = self.prepare_msg()

    def prepare_msg(self):
        msg = MIMEMultipart()
        msg['From'], msg['To'] = self.from_addr, self.to_addr
        msg['Subject'] = self.subject
        msg.attach(MIMEText(self.message.encode("utf-8"), "plain", "utf-8"))
        return msg


class ServerManager:
    def __init__(self):
        self.server = None

    def connect(self, host, ports):
        for port in ports:
            try:
                self.server = smtplib.SMTP(host, port)
                self.server.starttls()
                return True
            except:
                pass
        raise ConnectionError('No one port not found!')

    def login(self, user, password):
        try:
            self.server.login(user, password)
            return True
        except Exception as e:
            raise ConnectionError(e)

    def send_message(self, message):
        try:
            self.server.sendmail(message['From'], message['To'], message.as_string())
            return True
        except Exception as e:
            raise ConnectionError(e)

    def close(self):
        try:
            self.server.quit()
        except Exception as e:
            raise ConnectionAbortedError(e)


def mail_manager(subject, message, to, login, password, host=None, port=None):
    try:
        config = {"host": host or "smtp.gmail.com", "port": port or [25, 587, 465],
                  "login": login, "password": password,
                  "subject": str(subject),
                  "to": to,
                  "message": str(message),
                  }

        send_mail = SendMail(**config)
        send_mail.connect_and_send()
    except Exception as e:
        print(str(e))


def send_message(to, subject, message):
    mail_manager(subject, message, to, DEFAULT_EMAIL, DEFAULT_EMAIL_PASSWORD)
