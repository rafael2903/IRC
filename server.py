import os
import socket
import sys
import threading
from datetime import datetime


def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(0)
    try:
        s.connect(('8.8.8.8', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP


socket_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
ip = get_ip()
port = 6667
socket_server.bind((ip, port))

clients = []
channels = {}

socket_server.listen()
print(f"Servidor iniciado em {ip} na porta {port}")

COMMANDS = {
    "/JOIN": {
        "min_params": 1,
    },
    "/QUIT": {
        "min_params": 0,
    },
    "/USER": {
        "min_params": 4,
    },
    "/NICK": {
        "min_params": 1,
    },
    "/LIST": {
        "min_params": 0,
    },
    "/PART": {
        "min_params": 1,
    },
    "/WHO": {
        "min_params": 1,
    },
    "/PRIVMSG": {
        "min_params": 2,
    }
}


def send_message_to_channel(channel, message, sender_socket=None):
    if channel not in channels:
        return
    for client_socket in channels[channel]:
        if client_socket != sender_socket:
            client_socket.send(message.encode("utf-8"))


def send_message_to_client(nick, message):
    client_socket = find_socket_by_nickname(nick)
    client_socket.send(message.encode("utf-8"))


def find_client_by_socket(client_socket):
    for client in clients:
        if client["socket"] == client_socket:
            return client


def find_socket_by_nickname(nick):
    for client in clients:
        if client["nick"] == nick:
            return client["socket"]


def find_channel_by_client_socket(client_socket):
    for channel, members in channels.items():
        for member in members:
            if member == client_socket:
                return channel


def verify_registration(client_socket):
    client = find_client_by_socket(client_socket)
    if (not "nick" in client) or (not "username" in client):
        return False
    return True


def remove_member_from_channel(client_socket, channel):
    channels[channel].remove(client_socket)
    if len(channels[channel]) == 0:
        channels.pop(channel)
    else:
        client = find_client_by_socket(client_socket)
        send_message_to_channel(
            channel, f"* {client['nick']} saiu", client_socket)


def remove_client_from_server(client_socket):
    client = find_client_by_socket(client_socket)
    channel = find_channel_by_client_socket(client_socket)
    if channel:
        remove_member_from_channel(client_socket, channel)
        send_message_to_channel(channel, f"* {client['nick']} saiu")
    clients.remove(client)


def handle_join(*args):
    client_socket, params = args
    channel = params[0]
    old_channel = find_channel_by_client_socket(client_socket)

    if old_channel and old_channel != channel:
        remove_member_from_channel(client_socket, old_channel)

    if channel not in channels:
        channels[channel] = [client_socket]
        return f"* Você agora está no canal {channel}"
    elif client_socket not in channels[channel]:
        client = find_client_by_socket(client_socket)
        send_message_to_channel(channel, f"* {client['nick']} entrou")
        channels[channel].append(client_socket)
        return f"* Você agora está no canal {channel}"
    else:
        return f"* Você já está no canal {channel}"


def handle_quit(*args):
    client_socket = args[0]
    remove_client_from_server(client_socket)
    client_socket.close()
    sys.exit()


def handle_part(*args):
    client_socket, params = args
    channel = find_channel_by_client_socket(client_socket)
    if not channel:
        return f'ERR_NOTONCHANNEL'

    if channel in params:
        remove_member_from_channel(client_socket, channel)
        return f"* Você saiu do canal {channel}"
    else:
        return f'ERR_NOTONCHANNEL'


def handle_user(*args):
    client_socket, params = args
    params = ' '.join(params)
    user_infos, realname = params.split(":", 1)
    user_infos = user_infos.split(" ")

    client = find_client_by_socket(client_socket)
    client["username"] = user_infos[0]
    client["hostname"] = user_infos[1]
    client["servername"] = user_infos[2]
    client["realname"] = realname


def handle_nick(*args):
    client_socket, params = args
    newnick = params[0]
    client = find_client_by_socket(client_socket)

    if newnick in [client["nick"] for client in clients if "nick" in client]:
        return f"ERR_NICKNAMEINUSE"

    if "nick" not in client:
        client["nick"] = newnick
        return f"* Nickname atribuido para {newnick}"
    else:
        oldnick = client["nick"]
        client["nick"] = newnick
        channel = find_channel_by_client_socket(client_socket)
        if channel:
            send_message_to_channel(
                channel, f"* {oldnick} alterado para {newnick}", client_socket)
        return f"* Nickname alterado para {newnick}"


def handle_list(*args):
    response = "*** Channel\tUsers"
    for channel, members in channels.items():
        response += f"\n*** {channel}\t{len(members)}"
    return response


def handle_who(*args):
    client_socket, params = args
    names = ' '.join(params).split(',')

    for name in names:
        if name in channels.keys():
            response = f'\n*** Usuários no canal {name}'
            response += f'\n*** Username\tNickname\tHostname\tServername\tRealname'
            for user in channels[name]:
                client = find_client_by_socket(user)
                response += f'\n*** {client["username"]}\t{client["nick"]}\t{client["hostname"]}\t{client["servername"]}\t{client["realname"]}'
                client_socket.send(response.encode("utf-8"))
        else:
            who_clients = [
                client for client in clients if client["nick"] == name]
            if len(who_clients) > 0:
                client = who_clients[0]
                response = f'\n*** Informações do usuário {name}'
                response += f'\n*** Username\tNickname\tHostname\tServername\tRealname'
                response += f'\n*** {client["username"]}\t{client["nick"]}\t{client["hostname"]}\t{client["servername"]}\t{client["realname"]}'
                client_socket.send(response.encode("utf-8"))


def handle_privmsg(*args):
    client_socket, params = args
    params = ' '.join(params)
    names, message = params.split(":", 1)
    names = names.strip().split(",")

    for name in names:
        if name in [client["nick"] for client in clients]:
            send_message_to_client(name, message)
        elif name in channels:
            send_message_to_channel(name, message, client_socket)


def parse_command(data):
    parts = data.strip().split()
    command = parts[0].upper()
    params = parts[1:]
    return command, params


def validate_command(command, params):
    if command not in COMMANDS:
        return "ERR_UNKNOWNCOMMAND"

    min_params = COMMANDS[command]["min_params"]

    if len(params) < min_params:
        return f"ERR_NEEDMOREPARAMS"


handlers = {
    "/JOIN": handle_join,
    "/QUIT": handle_quit,
    "/USER": handle_user,
    "/NICK": handle_nick,
    "/LIST": handle_list,
    "/PART": handle_part,
    "/WHO": handle_who,
    "/PRIVMSG": handle_privmsg
}


def process_command(command, params, client_socket):
    error = validate_command(command, params)
    if error is not None:
        return error

    if command not in ["/USER", "/NICK", "/QUIT"]:
        registered = verify_registration(client_socket)
        if not registered:
            return f'ERR_NOTREGISTERED'

    return handlers[command](client_socket, params)


def handle_client(client_socket):
    clients.append({"socket": client_socket})
    while True:
        data = client_socket.recv(1024).decode("utf-8")
        if not data:
            remove_client_from_server(client_socket)
            break
        is_command = data.startswith("/")
        if is_command:
            command, params = parse_command(data)
            response = process_command(command, params, client_socket)
            if response:
                client_socket.send(response.encode("utf-8"))
        else:
            channel = find_channel_by_client_socket(client_socket)
            if channel:
                now = datetime.now()
                current_time = now.strftime("%H:%M:%S")
                client = find_client_by_socket(client_socket)
                message = f'\033[1m[{current_time}] <{client["nick"]}>:\033[0m ' + data
                send_message_to_channel(channel, message)
            else:
                client_socket.send(
                    "* Você não está em nenhum canal".encode("utf-8"))


while True:
    try:
        client_socket, client_address = socket_server.accept()
        print("Nova conexão a partir de", client_address)
        client_thread = threading.Thread(
            target=handle_client, args=(client_socket,))
        client_thread.start()
    except KeyboardInterrupt:
        print("\nEncerrando servidor...")
        os._exit(1)
