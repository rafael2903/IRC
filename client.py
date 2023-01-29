import os
import socket
import threading
import getpass

from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import FuzzyCompleter, WordCompleter
from prompt_toolkit.patch_stdout import patch_stdout

colors = {
    'red': '\033[31m{}\033[00m',
    'green': '\033[32m{}\033[00m',
    'yellow': '\033[33m{}\033[00m',
}


def colored(text, color):
    return colors[color].format(text)


def clear_terminal():
    os.system('cls' if os.name == 'nt' else 'clear')

clear_terminal()
client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)


while True:
    global server_ip
    global server_port
    server_ip = input("Digite o IP do servidor IRC: ")
    server_port = input("Digite a porta do servidor IRC: ")
    try:
        client_socket.connect((server_ip, int(server_port)))
        clear_terminal()
        print(
            colored(f"Conectado ao servidor {server_ip} na porta {server_port}", "green"))
        break
    except:
        print(colored("Não foi possível conectar ao servidor. Tente novamente.", "red"))

while True:
    nickname = input("Escolha um apelido: ")
    client_socket.send(f"/NICK {nickname}".encode("utf-8"))
    response = client_socket.recv(1024).decode("utf-8")
    if response == 'ERR_NICKNAMEINUSE':
        print(colored("Este apelido já está em uso. Escolha outro.", "red"))
    else:
        print(colored(response, "yellow"))
        username = nickname
        hostname = socket.gethostname()
        servername = server_ip
        realname = getpass.getuser()
        client_socket.send(
            f"/USER {username} {hostname} {servername} :{realname}".encode("utf-8"))
        break


def handle_output():
    while True:
        data = client_socket.recv(1024).decode("utf-8")
        if data:
            if data.startswith("ERR"):
                print(colored(data, "red"))
            elif data.startswith("*"):
                print(colored(data, "yellow"))
            else:
                print(data)
        else:
            os._exit(1)


output_thread = threading.Thread(target=handle_output)
output_thread.start()

commands_completer = WordCompleter(
    ['/JOIN', '/LIST', '/NICK', '/PART', '/QUIT', '/USER', '/PRIVMSG', '/WHO'])

session = PromptSession()

while True:
    with patch_stdout(raw=True):
        try:
            data = session.prompt('> ', completer=FuzzyCompleter(
                commands_completer), auto_suggest=AutoSuggestFromHistory())
            client_socket.send(data.encode("utf-8"))
        except KeyboardInterrupt or EOFError:
            print("Saindo...")
            client_socket.send("/QUIT".encode("utf-8"))
            break
