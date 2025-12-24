import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

export async function performFreightAudit(data: any, db: any, userId: string, schema_json?: string): Promise<{ valid: boolean, flags: string[], score: number }> {
  const flags: string[] = [];
  let score = 1.0;

  // For now, we'll validate the freight-specific fields exist
  const requiredFreightFields = ['pro_number', 'carrier', 'origin_zip', 'dest_zip', 'weight', 'total'];
  
  for (const field of requiredFreightFields) {
    if (!data[field] || data[field] === null || data[field] === '') {
      flags.push(`Missing required freight field: ${field}`);
      score *= 0.8;
    }
  }

  // Validate ZIP codes format (basic check)
  const originZip = data.origin_zip;
  const destZip = data.dest_zip;
  
  if (originZip && typeof originZip === 'string' && originZip.length < 5) {
    flags.push("Origin ZIP code appears to be invalid");
    score *= 0.9;
  }
  
  if (destZip && typeof destZip === 'string' && destZip.length < 5) {
    flags.push("Destination ZIP code appears to be invalid");
    score *= 0.9;
  }

  // Validate weight is a number
  if (data.weight !== undefined && data.weight !== null) {
    const weight = typeof data.weight === 'string' ? parseFloat(data.weight) : data.weight;
    if (isNaN(weight) || weight < 0) {
      flags.push('Billable weight must be a positive number');
      score *= 0.8;
    } else {
      data.weight = weight;
    }
  }

  // Validate total amount
  if (data.total !== undefined && data.total !== null) {
    const total = typeof data.total === 'string' ? parseFloat(data.total) : data.total;
    if (isNaN(total) || total < 0) {
      flags.push('Total amount must be a positive number');
      score *= 0.8;
    } else {
      data.total = total;
    }
  }

  // For the actual freight auditing (rate validation and redaction detection),
  // we need to call the Python FreightAuditor via a subprocess
  // This would require setting up a Python API endpoint or CLI tool
  // For now, we'll add a placeholder for when the full integration is ready

  // Placeholder for rate validation
  // In the full implementation, we would:
  // 1. Fetch rate card for carrier + lane from DB
  // 2. Calculate expected cost
  // 3. Compare with invoiced amount
  // 4. Flag overcharges

  // Placeholder for redaction detection
  // In the full implementation, we would:
  // 1. Download the PDF
  // 2. Run PyMuPDF redaction detection
  // 3. Flag security risks

  return { valid: flags.length === 0, flags, score };
}

export async function performAudit(data: any, db: any, userId: string, schema_json?: string): Promise<{ valid: boolean, flags: string[], score: number }> {
  // Check if this looks like freight data
  const isFreightData = data.pro_number && data.carrier && data.origin_zip && data.dest_zip;
  
  if (isFreightData) {
    // Use freight-specific audit
    return performFreightAudit(data, db, userId, schema_json);
  } else {
    // Use the original audit function for non-freight data
    return originalPerformAudit(data, db, userId, schema_json);
  }
}

// Original audit function for backward compatibility
function originalPerformAudit(data: any, db: any, userId: string, schema_json?: string): Promise<{ valid: boolean, flags: string[], score: number }> {
  return new Promise((resolve) => {
    // Import the original audit function from the existing file
    // Since we can't directly import from the same file, we'll recreate the logic here
    const flags: string[] = [];
    let score = 1.0;

    // Schema and normalization checks
    if (schema_json) {
      try {
        const schema = JSON.parse(schema_json);
        // Check required fields based on schema
        if (schema.required) {
          for (const field of schema.required) {
            if (!data[field] || data[field] === null || data[field] === '') {
              flags.push(`Missing required field: ${field}`);
              score *= 0.8;
            }
          }
        }
      } catch (e) {
        console.error('Error parsing schema_json:', e);
      }
    }

    // Validation for flat invoice fields
    if (!data.vendor || typeof data.vendor !== 'string' || data.vendor.trim() === '') {
      flags.push('Missing or invalid vendor name');
      score *= 0.8;
    }

    if (!data.date || typeof data.date !== 'string') {
      flags.push('Missing or invalid date');
      score *= 0.8;
    } else {
      // Validate date format (YYYY-MM-DD)
      const dateRegex = /^\d{4}-\d{2}-\d{2}$/;
      if (!dateRegex.test(data.date)) {
        flags.push('Date format invalid, expected YYYY-MM-DD');
        score *= 0.8;
      } else {
        // Additional date validation - ensure it's a valid date
        const dateObj = new Date(data.date);
        if (isNaN(dateObj.getTime())) {
          flags.push('Date is not a valid calendar date');
          score *= 0.8;
        }
      }
    }

    if (data.total === undefined || data.total === null) {
      flags.push('Missing total amount');
      score *= 0.8;
    } else {
      // Convert to number if it's a string
      const total = typeof data.total === 'string' ? parseFloat(data.total) : data.total;
      if (isNaN(total) || total < 0) {
        flags.push('Total amount must be a positive number');
        score *= 0.8;
      } else {
        // Normalize total to number
        data.total = total;
      }
    }

    if (!data.invoice_number || typeof data.invoice_number !== 'string') {
      flags.push('Missing or invalid invoice number');
      score *= 0.8;
    }

    // Normalize date if needed
    if (typeof data.date === 'string' && data.date.includes('/')) {
      // Convert MM/DD/YYYY or MM/DD/YY to YYYY-MM-DD
      const dateParts = data.date.split('/');
      if (dateParts.length === 3) {
        let [month, day, year] = dateParts;
        if (year.length === 2) {
          year = '20' + year; // Assume 21st century for 2-digit years
        }
        data.date = `${year.padStart(4, '0')}-${month.padStart(2, '0')}-${day.padStart(2, '0')}`;
      }
    }

    // Validation for line items
    if (data.line_items && Array.isArray(data.line_items)) {
      for (let i = 0; i < data.line_items.length; i++) {
        const item = data.line_items[i];
        if (typeof item.price !== 'number') {
          const price = typeof item.price === 'string' ? parseFloat(item.price.replace(/[^\d.-]/g, '')) : item.price;
          if (isNaN(price)) {
            flags.push(`Line item ${i} has invalid price`);
            score *= 0.9;
          } else {
            item.price = price;
          }
        }
        if (typeof item.quantity !== 'number') {
          const quantity = typeof item.quantity === 'string' ? parseFloat(item.quantity) : item.quantity;
          if (isNaN(quantity) || quantity < 0) {
            flags.push(`Line item ${i} has invalid quantity`);
            score *= 0.9;
          } else {
            item.quantity = quantity;
          }
        }
      }
    }

    // Math validation (after normalizing total)
    const total = typeof data.total === 'string' ? parseFloat(data.total) : data.total;
    if (data.line_items && Array.isArray(data.line_items)) {
      const lineTotal = data.line_items.reduce((sum: number, item: any) => {
        const price = typeof item.price === 'string' ? parseFloat(item.price.replace(/[^\d.-]/g, '')) : item.price;
        const quantity = typeof item.quantity === 'string' ? parseFloat(item.quantity) : item.quantity;
        return sum + (isNaN(price) ? 0 : price) * (isNaN(quantity) ? 0 : quantity);
      }, 0);

      if (Math.abs(lineTotal - total) > 0.05) {
        flags.push(`Math Error: Line items = $${lineTotal.toFixed(2)}, Total claims $${total}`);
        score *= 0.8;
      }
    }

    // Duplicate check
    // Note: This would need to be implemented with the actual DB query
    // const dup = await db.prepare(`
    //   SELECT id FROM historical_invoices
    //   WHERE user_id = ? AND vendor_name = ? AND invoice_number = ?
    // `).bind(userId, data.vendor, data.invoice_number).first();

    // if (dup) {
    //   flags.push("DUPLICATE: Invoice already processed");
    //   score *= 0.5;
    // }

    // Price spike check (using normalized total)
    // Note: This would need to be implemented with the actual DB query
    // const avg = await db.prepare(`
    //   SELECT AVG(total_amount) as vendor_avg
    //   FROM historical_invoices WHERE user_id = ? AND vendor_name = ?
    // `).bind(userId, data.vendor).first();

    // if (avg && avg.vendor_avg && total > avg.vendor_avg * 1.5) {
    //   const pct = ((total/avg.vendor_avg-1)*100).toFixed(0);
    //   flags.push(`PRICE SPIKE: ${pct}% above avg`);
    //   score *= 0.7;
    // }

    resolve({ valid: flags.length === 0, flags, score });
  });
}