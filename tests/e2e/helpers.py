# tests/e2e/helpers.py
import subprocess

def clear_redis_keys(pattern):
    """
    Deletes keys from the Redis container matching a specific pattern.
    """
    command_to_run = f"redis-cli --scan --pattern '{pattern}' | xargs redis-cli DEL"
    
    cmd = [
        "docker", "compose",
        "exec",
        "-T",
        "redis",
        "sh",
        "-c", command_to_run
    ]
    
    subprocess.run(cmd, capture_output=True, text=True, check=True)
    print(f"Cleared Redis keys with pattern: {pattern}")