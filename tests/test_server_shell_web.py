"""Tests for nginx and the web-stack file commands."""
from tests.support import _connected_shell

def test_nginx_install_configure_and_enable(server_shell):
    _connected_shell(server_shell)
    server_shell.execute("apt update")
    server_shell.execute("apt install nginx")
    assert server_shell.state.system["services"]["nginx"]["installed"] is True

    server_shell.execute("mkdir -p /etc/nginx/sites-available")
    server_shell.state.set_file_content(
        "/etc/nginx/sites-available/app",
        "server {\n  listen 80;\n  root /var/www/maze;\n}\n",
    )
    server_shell.execute("ln -s /etc/nginx/sites-available/app /etc/nginx/sites-enabled/app")
    assert server_shell.state.filesystem["/etc/nginx/sites-enabled/app"]["type"] == "link"

    result = server_shell.execute("nginx -t")
    assert result.output == "nginx: the configuration file /etc/nginx/nginx.conf syntax is ok"


def test_nginx_t_reports_a_broken_block(server_shell):
    _connected_shell(server_shell)
    server_shell.execute("apt update")
    server_shell.execute("apt install nginx")
    server_shell.state.set_file_content(
        "/etc/nginx/sites-available/app",
        "server {\n  listen 80;\n  root /var/www/maze\n",
    )
    result = server_shell.execute("nginx -t")
    assert "nginx: [emerg] unexpected" in result.output
    assert "test failed" in result.output


def test_mkdir_chown_chmod_set_permissions(server_shell):
    _connected_shell(server_shell)
    server_shell.execute("apt update")
    server_shell.execute("apt install nginx")
    server_shell.execute("mkdir -p /var/www/maze")
    server_shell.execute("chown -R maze-admin:www-data /var/www/maze")
    server_shell.execute("chmod -R 755 /var/www/maze")
    node = server_shell.state.filesystem["/var/www/maze"]
    assert node["owner"] == "maze-admin:www-data"
    assert node["perms"] == "755"


def test_verification_commands_set_the_health_flags(server_shell):
    _connected_shell(server_shell)
    server_shell.execute("apt update")
    server_shell.execute("apt install nginx")
    server_shell.state.set_file_content(
        "/etc/nginx/sites-available/app",
        "server {\n  listen 80;\n  root /var/www/maze;\n}\n",
    )
    server_shell.execute("ln -s /etc/nginx/sites-available/app /etc/nginx/sites-enabled/app")
    server_shell.execute("systemctl enable --now nginx")
    server_shell.execute("mkdir -p /var/www/maze")
    server_shell.execute("chmod -R 755 /var/www/maze")

    server_shell.execute("systemctl status nginx")
    assert server_shell.state.system["health_verified"]["service_status_checked"] is True

    server_shell.execute("ss -tulpn")
    assert server_shell.state.system["health_verified"]["ports_checked"] is True

    server_shell.execute("curl -I http://localhost")
    assert server_shell.state.system["health_verified"]["logs_or_http_checked"] is True


def test_editing_the_site_after_linking_keeps_the_step_done(server_shell):
    _connected_shell(server_shell)
    server_shell.execute("apt update")
    server_shell.execute("apt install nginx")
    server_shell.state.set_file_content(
        "/etc/nginx/sites-available/app",
        "server {\n  listen 80;\n  root /var/www/maze;\n}\n",
    )
    server_shell.execute(
        "ln -s /etc/nginx/sites-available/app /etc/nginx/sites-enabled/app"
    )
    server_shell.state.set_file_content(
        "/etc/nginx/sites-available/app",
        "server {\n  listen 80;\n  root /var/www/maze;\n  index index.html;\n}\n",
    )

    steps = {step.id: step for step in server_shell.state.steps()}
    assert steps["nginx"].done is True


def test_cp_into_a_directory_copies_the_file_inside(server_shell):
    _connected_shell(server_shell)
    server_shell.execute("adduser maze-admin")
    server_shell.answer("secret")
    server_shell.answer("secret")
    server_shell.answer("")
    server_shell.execute("mkdir -p /home/maze-admin/.ssh")
    server_shell.execute("cp /root/.ssh/authorized_keys /home/maze-admin/.ssh/")
    server_shell.execute("chown -R maze-admin:maze-admin /home/maze-admin/.ssh")

    assert server_shell.state.filesystem["/home/maze-admin/.ssh"]["type"] == "dir"
    assert server_shell.state.system["users"]["maze-admin"]["has_ssh_key"] is True


def test_nginx_t_without_the_site_config(server_shell):
    _connected_shell(server_shell)
    server_shell.execute("apt update")
    server_shell.execute("apt install nginx")
    assert "no host configuration found" in server_shell.execute("nginx -t").output


def test_curl_non_localhost_host(server_shell):
    _connected_shell(server_shell)
    assert "Could not resolve host" in server_shell.execute("curl -I http://example.com").output


def test_curl_404_when_web_root_missing(server_shell):
    _connected_shell(server_shell)
    assert "404" in server_shell.execute("curl -I http://localhost").output


def test_curl_403_when_web_root_is_private(server_shell):
    _connected_shell(server_shell)
    server_shell.state.filesystem["/var/www/maze"] = {
        "type": "dir", "perms": "700", "owner": "root:root"
    }
    assert "403" in server_shell.execute("curl -I http://localhost").output


def test_tail_missing_file(server_shell):
    _connected_shell(server_shell)
    assert "cannot open" in server_shell.execute("tail -n 20 /var/log/nope.log").output


def test_tail_access_log_marks_health(server_shell):
    _connected_shell(server_shell)
    server_shell.execute("tail -n 20 /var/log/nginx/access.log")
    assert server_shell.state.system["health_verified"]["logs_or_http_checked"] is True


def test_journalctl_marks_health(server_shell):
    _connected_shell(server_shell)
    server_shell.execute("journalctl -u nginx")
    assert server_shell.state.system["health_verified"]["logs_or_http_checked"] is True


def test_chown_missing_operand(server_shell):
    _connected_shell(server_shell)
    assert "missing operand" in server_shell.execute("chown").output
