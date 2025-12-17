/**
 * Utility functions for Discord notifications
 */

interface DiscordEmbed {
  title?: string;
  description?: string;
  color?: number; // RGB color value
  fields?: Array<{
    name: string;
    value: string;
    inline?: boolean;
  }>;
  timestamp?: string;
  footer?: {
    text: string;
  };
}

interface DiscordWebhookPayload {
  content?: string;
  embeds?: DiscordEmbed[];
  username?: string;
  avatar_url?: string;
}

export class DiscordNotifier {
  private webhookUrl: string;

  constructor(webhookUrl?: string) {
    this.webhookUrl = webhookUrl || process.env.DISCORD_WEBHOOK_URL || '';
  }

  /**
   * Send a document processing notification to Discord
   */
  async sendDocumentNotification(
    documentId: string,
    userId: string,
    status: string,
    fileName: string,
    additionalInfo?: Record<string, any>
  ): Promise<boolean> {
    if (!this.webhookUrl) {
      console.warn('Discord webhook URL not configured');
      return false;
    }

    const embed: DiscordEmbed = {
      title: 'Document Processing Update',
      color: status === 'completed' ? 0x00ff00 : status === 'failed' ? 0xff0000 : 0xffff00, // Green, Red, Yellow
      fields: [
        { name: 'Document ID', value: documentId, inline: true },
        { name: 'User ID', value: userId, inline: true },
        { name: 'File Name', value: fileName, inline: false },
        { name: 'Status', value: status, inline: true },
        { name: 'Timestamp', value: new Date().toISOString(), inline: true },
      ],
      footer: {
        text: 'Docuflow Document Processing Service'
      },
      timestamp: new Date().toISOString()
    };

    if (additionalInfo) {
      Object.entries(additionalInfo).forEach(([key, value]) => {
        embed.fields?.push({
          name: key.charAt(0).toUpperCase() + key.slice(1),
          value: String(value),
          inline: true
        });
      });
    }

    const payload: DiscordWebhookPayload = {
      embeds: [embed],
      username: 'Docuflow Bot',
      avatar_url: 'https://example.com/docuflow-avatar.png' // Replace with actual avatar URL
    };

    try {
      const response = await fetch(this.webhookUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        console.error(`Failed to send Discord notification: ${response.status} ${response.statusText}`);
        return false;
      }

      console.log('Discord notification sent successfully');
      return true;
    } catch (error) {
      console.error('Error sending Discord notification:', error);
      return false;
    }
  }

  /**
   * Send a general notification to Discord
   */
  async sendGeneralNotification(message: string, title?: string): Promise<boolean> {
    if (!this.webhookUrl) {
      console.warn('Discord webhook URL not configured');
      return false;
    }

    const embed: DiscordEmbed = {
      title: title || 'Notification',
      description: message,
      color: 0x007bff, // Bootstrap primary blue
      timestamp: new Date().toISOString(),
      footer: {
        text: 'Docuflow Document Processing Service'
      }
    };

    const payload: DiscordWebhookPayload = {
      embeds: [embed],
      username: 'Docuflow Bot'
    };

    try {
      const response = await fetch(this.webhookUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        console.error(`Failed to send Discord notification: ${response.status} ${response.statusText}`);
        return false;
      }

      console.log('Discord notification sent successfully');
      return true;
    } catch (error) {
      console.error('Error sending Discord notification:', error);
      return false;
    }
  }
}