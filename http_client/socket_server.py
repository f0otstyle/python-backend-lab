import socket
import logging

HOST = "127.0.0.1"
PORT = 65431

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='server.log',
    encoding='utf-8',
    filemode='w',
)

logger = logging.getLogger('api')


def main():
    logger.info("ЗАПУСК СЕРВЕРА")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        logger.info(f"Привязываемся к {HOST}:{PORT}...")
        s.bind((HOST, PORT))
        logger.info("Начинаем слушать...")
        s.listen()
        logger.info(f"Сервер запущен на {HOST}:{PORT}")
        logger.info("Ожидаем подключение клиента...")
        conn, addr = s.accept()
        logger.info(f"ПОДКЛЮЧИЛСЯ КЛИЕНТ: {addr}")
        with conn:
            logger.info(f"Connected by {addr}")
            while True:
                data = conn.recv(1024)
                if not data:
                    logger.error("Соединение закрыто")
                    break
                response = """HTTP/1.1 200 OK
Content-Type: text/plain
Content-Length: 13
Hello, World!"""
                conn.sendall(response.encode())
                break


if __name__ == "__main__":
    main()
