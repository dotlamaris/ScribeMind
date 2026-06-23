import os
import time
import json
from datetime import datetime
from name_utils import coolName
from pytz import timezone

pdt = timezone('America/Los_Angeles')


class CustomJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles non-serializable types as a failsafe"""
    def default(self, obj):
        try:
            if isinstance(obj, set):
                return list(obj)
            return super().default(obj)
        except TypeError:
            return str(obj)


class ExecutionLogger:
    global_logs = {}
    execution_counts = {}
    active_logger_stack = []
    server_session_id = None

    @classmethod
    def initialize_server_session(cls):
        """Generate a unique server session ID on startup"""
        if cls.server_session_id is None:
            cls.server_session_id = coolName(type="guild", seed=True)
            print(f"[LOGGER] Server session initialized: {cls.server_session_id}")

    def __init__(self, log_file="debug.txt"):
        self.log_file = log_file
        self.start_time = time.time()
        self.log_id = coolName(type="guild", seed=True)
        self.log_buffer = []

        import inspect
        frame = inspect.currentframe().f_back
        self.root_function = frame.f_code.co_name

        self.call_stack = []
        current_frame = frame
        while current_frame:
            self.call_stack.append({
                "function": current_frame.f_code.co_name,
                "file": os.path.basename(current_frame.f_code.co_filename),
                "line": current_frame.f_lineno
            })
            current_frame = current_frame.f_back
            if len(self.call_stack) > 10:
                break

        self.parent_execution_key = None
        if len(ExecutionLogger.active_logger_stack) > 0:
            self.parent_execution_key = ExecutionLogger.active_logger_stack[-1]

        if self.root_function not in ExecutionLogger.execution_counts:
            ExecutionLogger.execution_counts[self.root_function] = 0
        ExecutionLogger.execution_counts[self.root_function] += 1

        self.execution_index = ExecutionLogger.execution_counts[self.root_function]
        self.execution_key = f"{self.root_function}_{self.execution_index}"

        ExecutionLogger.active_logger_stack.append(self.execution_key)

    def __del__(self):
        if hasattr(self, 'execution_key') and self.execution_key in ExecutionLogger.active_logger_stack:
            ExecutionLogger.active_logger_stack.remove(self.execution_key)
        if hasattr(self, 'log_buffer') and len(self.log_buffer) > 0:
            self.commit()

    def get_current_time_pdt(self):
        return datetime.now(pdt).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

    def _truncate_strings(self, data, max_length=200, max_items=12):
        if isinstance(data, str):
            if len(data) > max_length:
                return f"{data[:max_length]}... [truncated {len(data) - max_length} chars]"
            return data
        elif isinstance(data, dict):
            if len(data) > max_items:
                truncated = {}
                for i, (k, v) in enumerate(data.items()):
                    if i < max_items:
                        truncated[k] = self._truncate_strings(v, max_length, max_items)
                    else:
                        break
                remaining = len(data) - max_items
                truncated[f"__{remaining}_more_entries__"] = f"{remaining} more entries..."
                return truncated
            else:
                return {k: self._truncate_strings(v, max_length, max_items) for k, v in data.items()}
        elif isinstance(data, list):
            if len(data) > max_items:
                truncated = [self._truncate_strings(item, max_length, max_items) for item in data[:max_items]]
                remaining = len(data) - max_items
                truncated.append(f"...{remaining} more entries...")
                return truncated
            else:
                return [self._truncate_strings(item, max_length, max_items) for item in data]
        else:
            return data

    def log(self, message, log_type="INFO", log_data=None, truncate=True):
        import inspect
        frame = inspect.currentframe().f_back

        elapsed_ms = round((time.time() - self.start_time) * 1000, 2)
        processed_data = self._truncate_strings(log_data) if (log_data and truncate) else log_data

        log_entry = {
            "formatted_time": self.get_current_time_pdt(),
            "elapsed_ms": elapsed_ms,
            "function": frame.f_code.co_name or None,
            "line": frame.f_lineno or None,
            "file": os.path.basename(frame.f_code.co_filename) or None,
            "message": message,
            "type": log_type,
            "data": processed_data
        }

        self.log_buffer.append(log_entry.copy())

        console_msg = f"[{log_type}] {log_entry['function']}:{log_entry['line']} - {message} ({elapsed_ms}ms)"
        print(console_msg)

        return log_entry

    @staticmethod
    def logs_to_json_string(logs_dict):
        try:
            return json.dumps(logs_dict, indent=2)
        except Exception as e:
            print(f"[LOGGER ERROR] Standard JSON failed: {e}")

        try:
            return json.dumps(logs_dict, indent=2, cls=CustomJSONEncoder)
        except Exception as e:
            print(f"[LOGGER JSON ERROR] CustomJSONEncoder failed: {e}")

        return str(logs_dict)

    def commit(self):
        if len(self.log_buffer) > 0:
            total_duration = self.log_buffer[-1]["elapsed_ms"] if self.log_buffer else 0

            execution_object = {
                "server_session_id": ExecutionLogger.server_session_id,
                "execution_key": self.execution_key,
                "function_name": self.log_buffer[0]["function"] if self.log_buffer else None,
                "duration_ms": total_duration,
                "parent_execution": self.parent_execution_key,
                "log_entries": self.log_buffer.copy(),
                "metadata": {
                    "log_id": self.log_id,
                    "root_function": self.log_buffer[0]["function"] if self.log_buffer else None,
                    "start_time": self.log_buffer[0]["formatted_time"] if self.log_buffer else None,
                    "file": self.log_buffer[0]["file"] if self.log_buffer else None,
                    "line": self.log_buffer[0]["line"] if self.log_buffer else None,
                    "end_time": self.log_buffer[-1]["formatted_time"] if self.log_buffer else None,
                    "call_stack": self.call_stack
                }
            }

            self.global_logs[self.execution_key] = execution_object
            self.log_buffer.clear()
