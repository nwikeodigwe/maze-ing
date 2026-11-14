"""Tests for systemctl and sshd."""
from tests.support import _connected_shell

def test_systemctl_reload_sshd_requires_valid_syntax(server_shell):
    _connected_shell(server_shell)
    server_shell.state.filesystem["/etc/ssh/sshd_config"]["parsed"]["syntax_valid"] = False
    result = server_shell.execute("systemctl reload sshd")
    assert result.output == (
        "Job for ssh.service failed because the control process exited with error code."
    )


def test_systemctl_enable_now_starts_nginx(server_shell):
    _connected_shell(server_shell)
    server_shell.execute("apt update")
    server_shell.execute("apt install nginx")
    server_shell.state.set_file_content(
        "/etc/nginx/sites-available/app",
        "server {\n  listen 80;\n  root /var/www/maze;\n}\n",
    )
    server_shell.execute("ln -s /etc/nginx/sites-available/app /etc/nginx/sites-enabled/app")
    server_shell.execute("systemctl enable --now nginx")
    assert server_shell.state.system["services"]["nginx"]["enabled"] is True
    assert server_shell.state.system["services"]["nginx"]["running"] is True


def test_sshd_t_reports_valid_config(server_shell):
    _connected_shell(server_shell)
    assert server_shell.execute("sshd -t").output == ""


def test_sshd_t_reports_invalid_config(server_shell):
    _connected_shell(server_shell)
    server_shell.state.filesystem["/etc/ssh/sshd_config"]["parsed"]["syntax_valid"] = False
    assert "Bad configuration option" in server_shell.execute("sshd -t").output


def test_systemctl_unknown_unit(server_shell):
    _connected_shell(server_shell)
    assert "not found" in server_shell.execute("systemctl status httpd").output


def test_systemctl_status_reports_service_health(server_shell):
    _connected_shell(server_shell)
    output = server_shell.execute("systemctl status sshd").output
    assert "active (running)" in output
    assert server_shell.state.system["health_verified"]["service_status_checked"] is True
