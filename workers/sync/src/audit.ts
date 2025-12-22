export async function performAudit(data: any, env: any, userId: string): Promise<{ valid: boolean, flags: string[], score: number }> {
  const flags: string[] = [];
  let score = 1.0;

  const lineTotal = data.line_items?.reduce((sum: number, item: any) => sum + (item.price * item.quantity), 0) || 0;
  if (Math.abs(lineTotal - data.total) > 0.05) {
    flags.push(`Math Error: Line items = $${lineTotal.toFixed(2)}, Total claims $${data.total}`);
    score *= 0.8;
  }

  const dup = await env.prepare(`
    SELECT id FROM historical_invoices 
    WHERE user_id = ? AND vendor_name = ? AND invoice_number = ?
  `).bind(userId, data.vendor, data.invoice_number).first();
  
  if (dup) {
    flags.push("DUPLICATE: Invoice already processed");
    score *= 0.5;
  }

  const avg = await env.prepare(`
    SELECT AVG(total_amount) as vendor_avg 
    FROM historical_invoices WHERE user_id = ? AND vendor_name = ?
  `).bind(userId, data.vendor).first();
  
  if (avg && avg.vendor_avg && data.total > avg.vendor_avg * 1.5) {
    const pct = ((data.total/avg.vendor_avg-1)*100).toFixed(0);
    flags.push(`PRICE SPIKE: ${pct}% above avg`);
    score *= 0.7;
  }

  return { valid: flags.length === 0, flags, score };
}