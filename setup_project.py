#!/usr/bin/env python3
import os
import re
import sys
import random
import argparse
from pathlib import Path


def generate_random_port(base_port):
    """Generate a random port number within a range to avoid conflicts."""
    return base_port + random.randint(0, 1000)


def replace_in_file(file_path, replacements):
    """Replace multiple patterns in a file."""
    if not os.path.exists(file_path):
        print(f"Warning: File {file_path} does not exist. Skipping.")
        return

    with open(file_path, 'r') as file:
        content = file.read()

    for old, new in replacements.items():
        content = content.replace(old, new)

    with open(file_path, 'w') as file:
        file.write(content)
    
    print(f"Updated {file_path}")


def update_docker_compose(project_name, postgres_port, redis_port, pgadmin_port, kafka_port):
    """Update the docker-compose.yml file with new project name and ports."""
    replacements = {
        'fastapitemplate-net': f'{project_name}-net',
        'fastapitemplate_redis_db': f'{project_name}_redis_db',
        'fastapitemplate_kafka': f'{project_name}_kafka',
        'POSTGRES_DB=fastapitemplate': f'POSTGRES_DB={project_name}',
        '30000:5432': f'{postgres_port}:5432',
        '30001:6379': f'{redis_port}:6379',
        '16543:80': f'{pgadmin_port}:80',
        '9092:9092': f'{kafka_port}:9092',
    }
    
    replace_in_file('docker-compose.yml', replacements)


def update_env_files(project_name, postgres_port, redis_port, kafka_port):
    """Update environment files with new project name and ports."""
    # Update .env.base
    base_replacements = {
        'SQL_DATABASE="fastapitemplate"': f'SQL_DATABASE="{project_name}"'
    }
    replace_in_file('.env.base', base_replacements)
    
    # Update .env.dev
    dev_replacements = {
        'SQL_PORT=30000': f'SQL_PORT={postgres_port}',
        'REDIS_PORT=30001': f'REDIS_PORT={redis_port}',
        'KAFKA_PORT="9092"': f'KAFKA_PORT="{kafka_port}"'
    }
    replace_in_file('.env.dev', dev_replacements)


def update_server_title(project_name):
    """Update the server title in server.py."""
    file_path = 'server.py'
    if not os.path.exists(file_path):
        print(f"Warning: File {file_path} does not exist. Skipping.")
        return
    
    with open(file_path, 'r') as file:
        content = file.read()
    
    # Replace the FastAPI title
    pattern = r'title="FastAPI Template"'
    replacement = f'title="{project_name.capitalize()}"'
    content = re.sub(pattern, replacement, content)
    
    # Replace the root endpoint message
    pattern = r'"FastAPI Template - Awake and ready to serve!"'
    replacement = f'"{project_name.capitalize()} - Awake and ready to serve!"'
    content = re.sub(pattern, replacement, content)
    
    with open(file_path, 'w') as file:
        file.write(content)
    
    print(f"Updated {file_path}")


def main():
    parser = argparse.ArgumentParser(description='Setup FastAPI project with custom name and ports.')
    parser.add_argument('--name', type=str, help='Project name (default: fastapi_project)')
    parser.add_argument('--postgres-port', type=int, help='PostgreSQL port (default: random)')
    parser.add_argument('--redis-port', type=int, help='Redis port (default: random)')
    parser.add_argument('--pgadmin-port', type=int, help='PGAdmin port (default: random)')
    parser.add_argument('--kafka-port', type=int, help='Kafka port (default: random)')
    
    args = parser.parse_args()
    
    # Set default project name if not provided
    project_name = args.name or 'fastapi_project'
    
    # Generate random ports if not provided
    postgres_port = args.postgres_port or generate_random_port(30000)
    redis_port = args.redis_port or generate_random_port(31000)
    pgadmin_port = args.pgadmin_port or generate_random_port(16000)
    kafka_port = args.kafka_port or generate_random_port(9000)
    
    print(f"Setting up project with name: {project_name}")
    print(f"Using ports: PostgreSQL={postgres_port}, Redis={redis_port}, PGAdmin={pgadmin_port}, Kafka={kafka_port}")
    
    # Update configuration files
    update_docker_compose(project_name, postgres_port, redis_port, pgadmin_port, kafka_port)
    update_env_files(project_name, postgres_port, redis_port, kafka_port)
    update_server_title(project_name)
    
    print("\nProject setup complete!")
    print(f"\nTo start your project, run:")
    print(f"  docker-compose up -d")
    print(f"\nTo access your API:")
    print(f"  http://localhost:8080")
    print(f"\nTo access PGAdmin:")
    print(f"  http://localhost:{pgadmin_port}")
    print(f"  Email: test@test.com")
    print(f"  Password: test")


if __name__ == "__main__":
    main()
