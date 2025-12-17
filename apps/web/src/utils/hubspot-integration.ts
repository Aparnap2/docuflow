/**
 * Utility functions for HubSpot integration
 */

interface HubSpotContact {
  email: string;
  firstname?: string;
  lastname?: string;
  [key: string]: string | undefined; // Allow additional properties
}

interface HubSpotDeal {
  dealname: string;
  amount?: string;
  dealstage?: string;
  pipeline?: string;
  [key: string]: string | undefined; // Allow additional properties
}

export class HubSpotIntegration {
  private apiKey: string;
  private baseUrl: string = 'https://api.hubapi.com';

  constructor(apiKey?: string) {
    this.apiKey = apiKey || process.env.HUBSPOT_API_KEY || '';
    if (!this.apiKey) {
      console.warn('HubSpot API key not configured');
    }
  }

  /**
   * Create or update a contact in HubSpot
   */
  async upsertContact(contactData: HubSpotContact): Promise<boolean> {
    if (!this.apiKey) {
      console.warn('HubSpot API key not configured');
      return false;
    }

    // Prepare the contact properties
    const properties = Object.entries(contactData).map(([property, value]) => ({
      property,
      value
    }));

    try {
      const response = await fetch(`${this.baseUrl}/contacts/v1/contact/createOrUpdate/email/${contactData.email}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${this.apiKey}`
        },
        body: JSON.stringify({
          properties
        })
      });

      if (!response.ok) {
        console.error(`Failed to upsert contact in HubSpot: ${response.status} ${response.statusText}`);
        return false;
      }

      console.log(`Contact ${contactData.email} upserted successfully in HubSpot`);
      return true;
    } catch (error) {
      console.error('Error upserting contact in HubSpot:', error);
      return false;
    }
  }

  /**
   * Create a deal in HubSpot
   */
  async createDeal(dealData: HubSpotDeal): Promise<string | null> {
    if (!this.apiKey) {
      console.warn('HubSpot API key not configured');
      return null;
    }

    // Prepare the deal properties
    const properties: { name: string; value: string }[] = [];
    Object.entries(dealData).forEach(([property, value]) => {
      if (value !== undefined) {
        properties.push({ name: property, value });
      }
    });

    try {
      const response = await fetch(`${this.baseUrl}/deals/v1/deal`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${this.apiKey}`
        },
        body: JSON.stringify({
          properties
        })
      });

      if (!response.ok) {
        console.error(`Failed to create deal in HubSpot: ${response.status} ${response.statusText}`);
        return null;
      }

      const result = await response.json();
      console.log(`Deal created successfully in HubSpot with ID: ${result.dealId}`);
      return result.dealId;
    } catch (error) {
      console.error('Error creating deal in HubSpot:', error);
      return null;
    }
  }

  /**
   * Associate a contact with a deal in HubSpot
   */
  async associateContactWithDeal(contactId: string, dealId: string): Promise<boolean> {
    if (!this.apiKey) {
      console.warn('HubSpot API key not configured');
      return false;
    }

    try {
      const response = await fetch(`${this.baseUrl}/crm-associations/v1/associations`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${this.apiKey}`
        },
        body: JSON.stringify({
          fromObjectId: contactId,
          toObjectId: dealId,
          category: 'HUBSPOT_DEFINED',
          definitionId: 5 // Contact to Deal association
        })
      });

      if (!response.ok) {
        console.error(`Failed to associate contact with deal in HubSpot: ${response.status} ${response.statusText}`);
        return false;
      }

      console.log(`Contact ${contactId} associated with deal ${dealId} successfully`);
      return true;
    } catch (error) {
      console.error('Error associating contact with deal in HubSpot:', error);
      return false;
    }
  }

  /**
   * Track an event in HubSpot for a contact (for usage tracking)
   */
  async trackContactEvent(
    contactEmail: string,
    eventName: string,
    properties: Record<string, string> = {}
  ): Promise<boolean> {
    if (!this.apiKey) {
      console.warn('HubSpot API key not configured');
      return false;
    }

    // First, get the contact ID by email
    const contactId = await this.getContactIdByEmail(contactEmail);
    if (!contactId) {
      console.error(`Could not find contact with email: ${contactEmail}`);
      return false;
    }

    try {
      // HubSpot doesn't have a direct event tracking API like some other platforms
      // Instead, we'll update a custom property to track the event
      const updateData: Record<string, string> = {
        ...properties,
        last_tracked_event: eventName,
        last_tracked_event_timestamp: new Date().toISOString()
      };

      const propertiesUpdate = Object.entries(updateData).map(([property, value]) => ({
        property,
        value
      }));

      const response = await fetch(`${this.baseUrl}/contacts/v1/contact/vid/${contactId}/profile`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${this.apiKey}`
        },
        body: JSON.stringify({
          properties: propertiesUpdate
        })
      });

      if (!response.ok) {
        console.error(`Failed to track event for contact in HubSpot: ${response.status} ${response.statusText}`);
        return false;
      }

      console.log(`Event "${eventName}" tracked for contact ${contactEmail} successfully`);
      return true;
    } catch (error) {
      console.error('Error tracking event for contact in HubSpot:', error);
      return false;
    }
  }

  /**
   * Helper method to get contact ID by email
   */
  private async getContactIdByEmail(email: string): Promise<string | null> {
    try {
      const response = await fetch(`${this.baseUrl}/contacts/v1/contact/email/${email}/profile?property=vid`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${this.apiKey}`
        }
      });

      if (!response.ok) {
        if (response.status === 404) {
          console.log(`Contact with email ${email} not found in HubSpot`);
          return null;
        }
        console.error(`Failed to get contact by email: ${response.status} ${response.statusText}`);
        return null;
      }

      const contact = await response.json();
      return contact.vid?.toString() || null;
    } catch (error) {
      console.error('Error getting contact by email from HubSpot:', error);
      return null;
    }
  }
}