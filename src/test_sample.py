"""Sample file to test CodeRev review capabilities."""


def calculate_sum(a, b):
    # No type hints, no docstring
    result = a + b
    return result


def process_data(data):
    # Potential bug: no null check
    items = data["items"]

    processed = []
    for i in range(len(items)):  # Could use enumerate
        item = items[i]
        if item["status"] == "active":
            processed.append(item)

    return processed


def fetch_user(user_id):
    # Hardcoded credentials (security issue)
    password = "admin123"

    # No error handling
    import requests

    response = requests.get(f"http://api.example.com/users/{user_id}")
    return response.json()


class DataProcessor:
    def __init__(self):
        self.data = []

    def add(self, item):
        self.data.append(item)

    def process(self):
        # Empty except block (bad practice)
        try:
            result = self._internal_process()
        except:
            pass
        return self.data

    def _internal_process(self):
        # Unused method
        pass


if __name__ == "__main__":
    print("Running sample")
