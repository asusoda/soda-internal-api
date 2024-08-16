import os
from dotenv import load_dotenv


class Config:
    def __init__(self) -> None:
        load_dotenv()
        try:
            # OAuth2 Config
            self.SECRET_KEY = os.environ["SECRET_KEY"]
            self.CLIENT_ID = os.environ["CLIENT_ID"]
            self.CLIENT_SECRET = os.environ["CLIENT_SECRET"]
            self.REDIRECT_URI = os.environ["REDIRECT_URI"]
            self.CLIENT_URL = os.environ["CLIENT_URL"]

            # API Tokens
            self.BOT_TOKEN = os.environ["BOT_TOKEN"]
            self.NOTION_TOKEN = os.environ["NOTION_TOKEN"]
            # Database Config
            self.DB_TYPE = os.environ["DB_TYPE"]
            self.DB_URI = os.environ["DB_URI"]
            self.DB_NAME = os.environ["DB_NAME"]
            self.DB_USER = os.environ["DB_USER"]
            self.DB_PASSWORD = os.environ["DB_PASSWORD"]

            # Encryption Config
            self.SSH_KEY = None
            with open("ssh.ppk", "r") as file:
                lines = file.readlines()
                print(lines)
                print(type(lines))
                public_lines_index = next(
                    i
                    for i, line in enumerate(lines)
                    if line.startswith("Public-Lines:")
                )
                private_lines_index = next(
                    i
                    for i, line in enumerate(lines)
                    if line.startswith("Private-Lines:")
                )

                # Extract the number of lines for the public and private keys
                public_lines_count = int(
                    lines[public_lines_index].split(":")[1].strip()
                )
                private_lines_count = int(
                    lines[private_lines_index].split(":")[1].strip()
                )

                # Extract the public key
                public_key_data = "".join(
                    lines[
                        public_lines_index + 1 : public_lines_index
                        + 1
                        + public_lines_count
                    ]
                )
                public_key_pem = f"-----BEGIN PUBLIC KEY-----\n{public_key_data.strip()}\n-----END PUBLIC KEY-----"

                # Extract the private key
                private_key_data = "".join(
                    lines[
                        private_lines_index + 1 : private_lines_index
                        + 1
                        + private_lines_count
                    ]
                )
                private_key_pem = f"-----BEGIN RSA PRIVATE KEY-----\n{private_key_data.strip()}\n-----END RSA PRIVATE KEY-----"
                self.SSH_KEY = (public_key_pem, private_key_pem)
            # App Config
            self.PROD = os.environ["PROD"]

        except KeyError as e:
            print(f"Missing environment variable: {e}")
            exit(1)

    def get(self, key: str) -> str:
        try:
            return getattr(self, key)
        except AttributeError:
            print(f"Key '{key}' not found in configuration.")
            exit(1)
