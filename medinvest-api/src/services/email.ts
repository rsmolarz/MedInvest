/**
 * Email Service
 */

import nodemailer from 'nodemailer';
import { config } from '../config';
import { logger } from '../utils/logger';

// Create transporter
const transporter = nodemailer.createTransport({
  host: config.smtp.host,
  port: config.smtp.port,
  secure: config.smtp.secure,
  auth: {
    user: config.smtp.user,
    pass: config.smtp.pass,
  },
});

// Verify connection on startup
if (config.smtp.user && config.smtp.pass) {
  transporter.verify()
    .then(() => logger.info('✅ Email service connected'))
    .catch((error) => logger.warn('⚠️ Email service not configured:', error.message));
}

/**
 * Send email
 */
async function sendEmail(to: string, subject: string, html: string) {
  if (!config.smtp.user || !config.smtp.pass) {
    logger.warn('Email service not configured, skipping email send');
    return;
  }
  
  try {
    await transporter.sendMail({
      from: config.smtp.from,
      to,
      subject,
      html,
    });
    logger.info(`Email sent to ${to}: ${subject}`);
  } catch (error) {
    logger.error('Failed to send email:', error);
    throw error;
  }
}

/**
 * Send verification email
 */
export async function sendVerificationEmail(
  email: string,
  name: string,
  token: string
) {
  const verifyUrl = `${config.appUrl}/verify-email?token=${token}`;
  const mobileUrl = `${config.mobileScheme}://verify-email?token=${token}`;
  
  const html = `
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <title>Verify Your Email</title>
    </head>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
      <div style="background: linear-gradient(135deg, #0066FF 0%, #0052CC 100%); padding: 30px; border-radius: 12px 12px 0 0; text-align: center;">
        <h1 style="color: white; margin: 0; font-size: 28px;">MedInvest</h1>
      </div>
      
      <div style="background: #fff; padding: 40px 30px; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 12px 12px;">
        <h2 style="margin-top: 0; color: #1f2937;">Welcome to MedInvest, ${name}!</h2>
        
        <p>Thank you for joining our community of medical professionals and investors. Please verify your email address to complete your registration.</p>
        
        <div style="text-align: center; margin: 30px 0;">
          <a href="${verifyUrl}" style="display: inline-block; background: #0066FF; color: white; padding: 14px 32px; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 16px;">Verify Email Address</a>
        </div>
        
        <p style="color: #6b7280; font-size: 14px;">If the button doesn't work, copy and paste this link into your browser:</p>
        <p style="color: #0066FF; word-break: break-all; font-size: 14px;">${verifyUrl}</p>
        
        <p style="color: #6b7280; font-size: 14px;">On mobile? <a href="${mobileUrl}" style="color: #0066FF;">Open in app</a></p>
        
        <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 30px 0;">
        
        <p style="color: #9ca3af; font-size: 12px; margin-bottom: 0;">This link will expire in 24 hours. If you didn't create an account with MedInvest, you can safely ignore this email.</p>
      </div>
      
      <div style="text-align: center; padding: 20px; color: #9ca3af; font-size: 12px;">
        <p>© ${new Date().getFullYear()} MedInvest. All rights reserved.</p>
      </div>
    </body>
    </html>
  `;
  
  await sendEmail(email, 'Verify your MedInvest email', html);
}

/**
 * Send password reset email
 */
export async function sendPasswordResetEmail(
  email: string,
  name: string,
  token: string
) {
  const resetUrl = `${config.appUrl}/reset-password?token=${token}`;
  const mobileUrl = `${config.mobileScheme}://reset-password?token=${token}`;
  
  const html = `
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <title>Reset Your Password</title>
    </head>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
      <div style="background: linear-gradient(135deg, #0066FF 0%, #0052CC 100%); padding: 30px; border-radius: 12px 12px 0 0; text-align: center;">
        <h1 style="color: white; margin: 0; font-size: 28px;">MedInvest</h1>
      </div>
      
      <div style="background: #fff; padding: 40px 30px; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 12px 12px;">
        <h2 style="margin-top: 0; color: #1f2937;">Reset Your Password</h2>
        
        <p>Hi ${name},</p>
        
        <p>We received a request to reset your password. Click the button below to choose a new password:</p>
        
        <div style="text-align: center; margin: 30px 0;">
          <a href="${resetUrl}" style="display: inline-block; background: #0066FF; color: white; padding: 14px 32px; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 16px;">Reset Password</a>
        </div>
        
        <p style="color: #6b7280; font-size: 14px;">If the button doesn't work, copy and paste this link:</p>
        <p style="color: #0066FF; word-break: break-all; font-size: 14px;">${resetUrl}</p>
        
        <p style="color: #6b7280; font-size: 14px;">On mobile? <a href="${mobileUrl}" style="color: #0066FF;">Open in app</a></p>
        
        <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 30px 0;">
        
        <p style="color: #9ca3af; font-size: 12px; margin-bottom: 0;">This link will expire in 1 hour. If you didn't request a password reset, you can safely ignore this email.</p>
      </div>
      
      <div style="text-align: center; padding: 20px; color: #9ca3af; font-size: 12px;">
        <p>© ${new Date().getFullYear()} MedInvest. All rights reserved.</p>
      </div>
    </body>
    </html>
  `;
  
  await sendEmail(email, 'Reset your MedInvest password', html);
}

/**
 * Send notification email
 */
export async function sendNotificationEmail(
  email: string,
  name: string,
  subject: string,
  message: string,
  actionUrl?: string,
  actionText?: string
) {
  const html = `
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <title>${subject}</title>
    </head>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
      <div style="background: linear-gradient(135deg, #0066FF 0%, #0052CC 100%); padding: 30px; border-radius: 12px 12px 0 0; text-align: center;">
        <h1 style="color: white; margin: 0; font-size: 28px;">MedInvest</h1>
      </div>
      
      <div style="background: #fff; padding: 40px 30px; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 12px 12px;">
        <p>Hi ${name},</p>
        
        <p>${message}</p>
        
        ${actionUrl && actionText ? `
          <div style="text-align: center; margin: 30px 0;">
            <a href="${actionUrl}" style="display: inline-block; background: #0066FF; color: white; padding: 14px 32px; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 16px;">${actionText}</a>
          </div>
        ` : ''}
      </div>
      
      <div style="text-align: center; padding: 20px; color: #9ca3af; font-size: 12px;">
        <p>© ${new Date().getFullYear()} MedInvest. All rights reserved.</p>
        <p><a href="${config.appUrl}/settings/notifications" style="color: #9ca3af;">Manage notification preferences</a></p>
      </div>
    </body>
    </html>
  `;
  
  await sendEmail(email, subject, html);
}
