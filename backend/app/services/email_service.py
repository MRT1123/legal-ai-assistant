"""
邮件服务

负责：
- 生成验证码
- 发送邮件（预留完整 SMTP 接口，开发阶段验证码打印到控制台）

使用方式：
- 开发环境：不配置环境变量，验证码直接打印到控制台
- 生产环境：设置 SMTP_HOST / SMTP_USER / SMTP_PASS 等环境变量，自动切换为真实发送
"""

import os
import random
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional


class EmailService:
    """邮件发送服务"""

    def __init__(self):
        """
        初始化邮件服务
        从环境变量读取 SMTP 配置，有配置则启用真实发送，否则走控制台模式
        """
        # SMTP 配置（通过环境变量设置，部署时填入即可）
        self.smtp_host = os.getenv("SMTP_HOST", "")          # 如 smtp.qq.com / smtp.gmail.com
        self.smtp_port = int(os.getenv("SMTP_PORT", "465"))  # SSL 端口，默认 465
        self.smtp_user = os.getenv("SMTP_USER", "")          # 发件邮箱地址
        self.smtp_pass = os.getenv("SMTP_PASS", "")          # 邮箱授权码（不是登录密码）
        self.smtp_sender_name = os.getenv("SMTP_SENDER_NAME", "法律智能助手")  # 发件人显示名称
        
        # 是否启用真实发送（有 SMTP 配置才启用）
        self.enabled = bool(self.smtp_host and self.smtp_user and self.smtp_pass)
        
        if self.enabled:
            print(f"[邮件] 邮件服务已启用 SMTP：{self.smtp_host}:{self.smtp_port}")
        else:
            print("[邮件] 邮件服务处于开发模式（验证码将打印到控制台，不实际发送）")

    def generate_code(self, length: int = 6) -> str:
        """
        生成随机验证码
        
        参数：
            length - 验证码长度，默认 6 位数字
        
        返回：验证码字符串
        """
        return ''.join([str(random.randint(0, 9)) for _ in range(length)])

    def send_verification_code(self, email: str, code: str, purpose: str) -> bool:
        """
        发送验证码到指定邮箱
        
        参数：
            email   - 接收验证码的邮箱
            code    - 验证码
            purpose - 用途："register"（注册）或 "reset"（重置密码）
        
        返回：发送成功返回 True，失败返回 False
        """
        # 根据用途生成不同的邮件标题和内容
        if purpose == "register":
            subject = "【法律智能助手】注册验证码"
            body = self._build_register_email(code)
        elif purpose == "reset":
            subject = "【法律智能助手】密码重置验证码"
            body = self._build_reset_email(code)
        else:
            subject = "【法律智能助手】验证码"
            body = f"您的验证码是：{code}，5 分钟内有效。"

        # 根据是否配置 SMTP 决定发送方式
        if self.enabled:
            return self._send_via_smtp(email, subject, body)
        else:
            return self._send_to_console(email, subject, code)

    def _build_register_email(self, code: str) -> str:
        """构建注册验证邮件的 HTML 内容"""
        return f"""
        <html>
        <body style="font-family: 'Microsoft YaHei', sans-serif; padding: 20px;">
            <h2 style="color: #667eea;">🎉 欢迎注册法律智能助手</h2>
            <p>您正在进行账号注册，验证码如下：</p>
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                        color: white; font-size: 32px; font-weight: bold; 
                        padding: 20px; text-align: center; border-radius: 8px;
                        margin: 20px 0; letter-spacing: 8px;">
                {code}
            </div>
            <p style="color: #999;">⏰ 验证码有效期为 <strong>5 分钟</strong>，请尽快使用。</p>
            <p style="color: #999;">如果您没有进行注册操作，请忽略此邮件。</p>
        </body>
        </html>
        """

    def _build_reset_email(self, code: str) -> str:
        """构建密码重置邮件的 HTML 内容"""
        return f"""
        <html>
        <body style="font-family: 'Microsoft YaHei', sans-serif; padding: 20px;">
            <h2 style="color: #f093fb;">🔑 密码重置验证</h2>
            <p>您正在进行密码重置操作，验证码如下：</p>
            <div style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); 
                        color: white; font-size: 32px; font-weight: bold; 
                        padding: 20px; text-align: center; border-radius: 8px;
                        margin: 20px 0; letter-spacing: 8px;">
                {code}
            </div>
            <p style="color: #999;">⏰ 验证码有效期为 <strong>5 分钟</strong>，请尽快使用。</p>
            <p style="color: #999;">如果您没有进行密码重置操作，请忽略此邮件，您的账号安全不受影响。</p>
        </body>
        </html>
        """

    def _send_via_smtp(self, email: str, subject: str, html_body: str) -> bool:
        """
        通过 SMTP 发送真实邮件
        
        参数：
            email     - 收件人邮箱
            subject   - 邮件标题
            html_body - 邮件 HTML 内容
        
        返回：发送成功返回 True，失败返回 False
        """
        try:
            # 构建邮件
            msg = MIMEMultipart("alternative")
            msg["From"] = f"{self.smtp_sender_name} <{self.smtp_user}>"
            msg["To"] = email
            msg["Subject"] = subject
            msg.attach(MIMEText(html_body, "html", "utf-8"))

            # 通过 SSL 连接 SMTP 服务器并发送
            with smtplib.SMTP_SSL(self.smtp_host, self.smtp_port) as server:
                server.login(self.smtp_user, self.smtp_pass)
                server.sendmail(self.smtp_user, email, msg.as_string())

            print(f"📧 邮件已发送至 {email}")
            return True

        except Exception as e:
            print(f"❌ 邮件发送失败：{str(e)}")
            return False

    def _send_to_console(self, email: str, subject: str, code: str) -> bool:
        """
        开发模式：将验证码打印到控制台（不实际发送邮件）
        
        返回：始终返回 True
        """
        print("\n" + "=" * 50)
        print(f"📧 [开发模式] 验证码发送")
        print(f"   收件人：{email}")
        print(f"   主  题：{subject}")
        print(f"   验证码：{code}")
        print(f"   有效期：5 分钟")
        print("=" * 50 + "\n")
        return True


# 全局单例（供路由直接引用）
email_service = EmailService()
