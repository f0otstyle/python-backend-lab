import socket
import logging

HOST = "127.0.0.1"
PORT = 65431


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='client.log',
    encoding='utf-8',
    filemode='w',
)

logger = logging.getLogger('api')


def parse_http_response(response: bytes):
    header, _, body = response.partition(b'\r\n\r\n')
    lines = header.split(b'\r\n')
    status_line = lines[0].decode('utf-8')

    headers = {}
    for line in lines[1:]:
        if b': ' in line:
            key, value = line.decode('utf-8').split(': ', 1)
            headers[key] = value

    return status_line, headers, body


def main():
    logger.info("ЗАПУСК КЛИЕНТА")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        logger.info("Подключаемся к {HOST}:{PORT}...")
        s.connect((HOST, PORT))
        logger.info("ПОДКЛЮЧЕНИЕ УСТАНОВЛЕНО!")
        request = "GET / HTTP/1.1\r\nHost: localhost\r\n\r\n"

        logger.info(f"ОТПРАВЛЯЕМ ЗАПРОС ({len(request)} байт):")

        s.sendall(request.encode())

        logger.info("Запрос отправлен!")

        logger.info("Ожидаем ответ от сервера...")
        response = b''
        while True:
            chunk = s.recv(1024)
            if not chunk:
                logger.error("Сервер закрыл соединение")
                break
            response += chunk

        log_lines = []
        status, headers, body = parse_http_response(response)

        log_lines.append("\nСТАРТОВАЯ СТРОКА:")
        log_lines.append(f"{status}")

        logger.info("\n".join(log_lines))
        logger.info("Соединение закрыто")


if __name__ == "__main__":
    main()
