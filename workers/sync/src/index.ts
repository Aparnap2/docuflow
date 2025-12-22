import { google } from 'googleapis';
import { performAudit } from './audit';

const SCOPES = ['https://www.googleapis.com/auth/spreadsheets'];

async function getSheetsClient(refreshToken: string) {
  const oauth2Client = new google.auth.OAuth2();
  oauth2Client.setCredentials({ refresh_token: refreshToken });
  return google.sheets({ version: 'v4', auth: oauth2Client });
}

export default {
  async queue(batch: any, env: any, ctx: any) {
    for (const message of batch.messages) {
      try {
        const { jobId, userId, r2Key } = message.body;
        
        const job = await env.DB.prepare(`
          SELECT j.*, u.google_refresh_token, u.target_sheet_id
          FROM jobs j
          JOIN users u ON j.user_id = u.id
          LEFT JOIN extractors e ON j.extractor_id = e.id
          WHERE j.id = ?
        `).bind(jobId).first();
        
        if (!job) {
          message.ack();
          continue;
        }

        const result = await env.DB.prepare(
          'SELECT extracted_json FROM jobs WHERE id = ?'
        ).bind(jobId).first();
        
        if (!result?.extracted_json) {
          message.ack();
          continue;
        }

        const data = JSON.parse(result.extracted_json);
        const audit = await performAudit(data, env.DB, userId);
        
        await env.DB.prepare(`
          UPDATE jobs SET 
            status = ?, audit_flags = ?, confidence_score = ?, updated_at = ?
          WHERE id = ?
        `).bind(audit.valid ? 'completed' : 'flagged', JSON.stringify(audit.flags), audit.score, Date.now(), jobId).run();

        const sheets = await getSheetsClient(job.google_refresh_token);
        const values = [
          data.date || '',
          data.vendor || '',
          data.total || '',
          audit.valid ? '✅ Clean' : `⚠️ ${audit.flags[0] || 'Review'}`,
          data.line_items?.length || 0,
          job.r2_visualization_url || ''
        ];
        
        await sheets.spreadsheets.values.append({
          spreadsheetId: job.target_sheet_id,
          range: 'A:Z',
          valueInputOption: 'RAW',
          resource: { values: [values] }
        });

        if (audit.valid) {
          await env.DB.prepare(`
            INSERT INTO historical_invoices 
            (id, user_id, vendor_name, invoice_number, total_amount, invoice_date, created_at, job_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
          `).bind(
            crypto.randomUUID(),
            userId,
            data.vendor,
            data.invoice_number,
            data.total,
            data.date,
            Date.now(),
            jobId
          ).run();
        }

        message.ack();
        
      } catch (error) {
        console.error('Sync failed:', error);
        const delay = Math.min(300, 2 ** message.attempts);
        message.retry(delay);
      }
    }
  }
};