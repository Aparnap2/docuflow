export default {
  async fetch(request: Request, env: any) {
    const url = new URL(request.url);
    
    if (url.pathname === '/create-checkout') {
      const { userId, plan } = await request.json();
      
      const checkout = await fetch('https://api.lemonsqueezy.com/v1/checkouts', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${env.LEMONSQEEZY_SECRET}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          store_id: plan === 'pro' ? 'PRO_ID' : 'STARTER_ID',
          customer_email: userId,
          custom_data: { userId }
        })
      });
      
      const checkoutData = await checkout.json();
      return Response.redirect(checkoutData.data.attributes.url, 302);
    }
    
    if (url.pathname === '/webhook') {
      const sig = request.headers.get('x-lemon-squeezy-signature');
      const body = await request.text();
      
      const webhookEvent = JSON.parse(body);
      
      if (webhookEvent.type === 'subscription_created') {
        const userId = webhookEvent.data.custom_data.userId;
        const plan = webhookEvent.data.product_id === 'PRO_ID' ? 'pro' : 'starter';
        
        await env.DB.prepare(
          `UPDATE users SET plan = ? WHERE id = ?`
        ).bind(plan, userId).run();
      }
      
      return new Response('OK');
    }
    
    return new Response('Not Found', { status: 404 });
  }
};