/**
 * Hybrid Search Implementation for DocuFlow v2.0
 * Combines vector similarity (Vectorize) with keyword search (D1)
 * Uses Reciprocal Rank Fusion (RRF) for result ranking
 */

export interface HybridSearchResult {
  id: string;
  score: number;
  vector_score?: number;
  keyword_score?: number;
  metadata?: any;
}

export interface SearchOptions {
  topK?: number;
  namespace?: string;
  includeMetadata?: boolean;
}

/**
 * Extract keywords from query text for keyword search
 * @param text - Input query text
 * @returns Array of extracted keywords
 */
export function extractKeywords(text: string): string[] {
  // Convert to lowercase and remove punctuation
  const cleanText = text.toLowerCase().replace(/[^\w\s]/g, ' ');
  
  // Split into words and filter
  const words = cleanText.split(/\s+/).filter(word => word.length > 3);
  
  // Remove common stop words
  const stopWords = new Set([
    'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'from',
    'up', 'about', 'into', 'through', 'during', 'before', 'after', 'above', 'below', 'between',
    'among', 'this', 'that', 'these', 'those', 'what', 'which', 'who', 'when', 'where', 'why',
    'how', 'all', 'any', 'both', 'each', 'few', 'more', 'most', 'other', 'some', 'such', 'no',
    'nor', 'not', 'only', 'own', 'same', 'so', 'than', 'too', 'very', 'can', 'will', 'just',
    'should', 'now', 'also', 'may', 'might', 'must', 'shall', 'would', 'could', 'should'
  ]);
  
  // Filter out stop words and return top keywords
  const keywords = words.filter(word => !stopWords.has(word));
  
  // Return top 10 most relevant keywords
  return keywords.slice(0, 10);
}

/**
 * Build keyword search query for D1
 * @param keywords - Array of keywords
 * @returns SQL WHERE clause
 */
export function buildKeywordQuery(keywords: string[]): string {
  if (keywords.length === 0) return "1=1";
  
  // Build OR conditions for each keyword
  const conditions = keywords.map(keyword => 
    `c.keywords LIKE '%${keyword}%' OR c.content_md LIKE '%${keyword}%'`
  );
  
  return `(${conditions.join(' OR ')})`;
}

/**
 * Perform hybrid search combining vector and keyword search
 * @param env - Cloudflare environment
 * @param query - Search query text
 * @param queryVector - Query embedding vector
 * @param projectId - Project ID for namespace
 * @param options - Search options
 * @returns Array of hybrid search results
 */
export async function hybridSearch(
  env: Env,
  query: string,
  queryVector: number[],
  projectId: string,
  options: SearchOptions = {}
): Promise<HybridSearchResult[]> {
  
  const topK = options.topK || 10;
  const namespace = options.namespace || projectId;
  
  console.log(`Hybrid search: query="${query}", topK=${topK}, project=${projectId}`);
  
  try {
    // 1. Vector search in Vectorize
    console.log("Performing vector search...");
    const vectorStart = Date.now();
    const vectorResults = await env.VECTORIZE.query(queryVector, {
      topK: topK * 2, // Get more candidates for RRF
      namespace: namespace,
      returnMetadata: "all"
    });
    const vectorTime = Date.now() - vectorStart;
    console.log(`Vector search completed in ${vectorTime}ms, found ${vectorResults.matches?.length || 0} results`);
    
    // 2. Keyword search in D1
    console.log("Performing keyword search...");
    const keywords = extractKeywords(query);
    console.log(`Extracted keywords: ${keywords.join(', ')}`);
    
    const keywordStart = Date.now();
    const keywordQuery = buildKeywordQuery(keywords);
    
    const keywordResults = await env.DB.prepare(`
      SELECT 
        c.id, 
        c.content_md, 
        c.keywords, 
        c.metadata_key, 
        c.page_number, 
        c.section_hierarchy,
        c.document_id,
        c.chunk_index,
        d.source_name,
        d.sha256
      FROM chunks c
      JOIN documents d ON c.document_id = d.id
      WHERE c.project_id = ? 
      AND d.status = 'READY'
      AND ${keywordQuery}
      ORDER BY c.chunk_index
      LIMIT ?
    `).bind(projectId, topK * 2).all();
    
    const keywordTime = Date.now() - keywordStart;
    console.log(`Keyword search completed in ${keywordTime}ms, found ${keywordResults.results?.length || 0} results`);
    
    // 3. Reciprocal Rank Fusion (RRF)
    console.log("Fusing results with RRF...");
    const fusedResults = fuseResults(
      vectorResults.matches || [], 
      keywordResults.results as any[] || [], 
      topK
    );
    
    console.log(`Hybrid search completed, returning ${fusedResults.length} results`);
    
    return fusedResults;
    
  } catch (error) {
    console.error("Hybrid search error:", error);
    throw new Error(`Hybrid search failed: ${error.message}`);
  }
}

/**
 * Fuse vector and keyword search results using Reciprocal Rank Fusion
 * @param vectorMatches - Vector search results
 * @param keywordMatches - Keyword search results  
 * @param topK - Number of top results to return
 * @returns Fused results ranked by RRF score
 */
function fuseResults(
  vectorMatches: any[],
  keywordMatches: any[],
  topK: number
): HybridSearchResult[] {
  
  const scores = new Map<string, { 
    vectorRank?: number; 
    keywordRank?: number; 
    data: any;
    vectorScore?: number;
  }>();
  
  console.log(`Fusing ${vectorMatches.length} vector results and ${keywordMatches.length} keyword results`);
  
  // Add vector results with ranks
  vectorMatches.forEach((match, index) => {
    scores.set(match.id, { 
      vectorRank: index + 1, 
      vectorScore: match.score || (1.0 - (index / vectorMatches.length)),
      data: match 
    });
  });
  
  // Add keyword results with ranks
  keywordMatches.forEach((match, index) => {
    const existing = scores.get(match.id) || { data: match };
    scores.set(match.id, { 
      ...existing, 
      keywordRank: index + 1 
    });
  });
  
  // Calculate RRF scores (k=60 is standard for RRF)
  const k = 60;
  const results = Array.from(scores.entries()).map(([id, score]) => {
    const vectorScore = score.vectorRank ? 1.0 / (k + score.vectorRank) : 0;
    const keywordScore = score.keywordRank ? 1.0 / (k + score.keywordRank) : 0;
    
    // Combine scores with equal weighting
    const finalScore = vectorScore + keywordScore;
    
    return {
      id,
      score: finalScore,
      vector_score: score.vectorRank ? 1.0 / score.vectorRank : undefined,
      keyword_score: score.keywordRank ? 1.0 / score.keywordRank : undefined,
      metadata: {
        ...score.data,
        // Add fusion metadata
        fusion: {
          vector_rank: score.vectorRank,
          keyword_rank: score.keywordRank,
          vector_contribution: vectorScore,
          keyword_contribution: keywordScore
        }
      }
    };
  });
  
  // Sort by final score and return top K
  const sortedResults = results
    .sort((a, b) => b.score - a.score)
    .slice(0, topK);
  
  console.log(`RRF fusion complete, top result score: ${sortedResults[0]?.score || 0}`);
  
  return sortedResults;
}

/**
 * Perform keyword-only search
 * @param env - Cloudflare environment
 * @param query - Search query text
 * @param projectId - Project ID
 * @param topK - Number of results
 * @returns Keyword search results
 */
export async function keywordSearch(
  env: Env,
  query: string,
  projectId: string,
  topK: number = 10
): Promise<HybridSearchResult[]> {
  
  console.log(`Keyword search: query="${query}", topK=${topK}, project=${projectId}`);
  
  const keywords = extractKeywords(query);
  const keywordQuery = buildKeywordQuery(keywords);
  
  try {
    const results = await env.DB.prepare(`
      SELECT 
        c.id, 
        c.content_md, 
        c.keywords, 
        c.metadata_key, 
        c.page_number, 
        c.section_hierarchy,
        c.document_id,
        c.chunk_index,
        d.source_name,
        d.sha256
      FROM chunks c
      JOIN documents d ON c.document_id = d.id
      WHERE c.project_id = ? 
      AND d.status = 'READY'
      AND ${keywordQuery}
      ORDER BY c.chunk_index
      LIMIT ?
    `).bind(projectId, topK).all();
    
    return (results.results as any[]).map((row, index) => ({
      id: row.id,
      score: 1.0 / (index + 1), // Simple rank-based scoring
      keyword_score: 1.0 / (index + 1),
      metadata: row
    }));
    
  } catch (error) {
    console.error("Keyword search error:", error);
    throw new Error(`Keyword search failed: ${error.message}`);
  }
}

/**
 * Perform vector-only search
 * @param env - Cloudflare environment
 * @param queryVector - Query embedding vector
 * @param projectId - Project ID
 * @param topK - Number of results
 * @returns Vector search results
 */
export async function vectorSearch(
  env: Env,
  queryVector: number[],
  projectId: string,
  topK: number = 10
): Promise<HybridSearchResult[]> {
  
  console.log(`Vector search: topK=${topK}, project=${projectId}`);
  
  try {
    const results = await env.VECTORIZE.query(queryVector, {
      topK: topK,
      namespace: projectId,
      returnMetadata: "all"
    });
    
    return (results.matches || []).map((match, index) => ({
      id: match.id,
      score: match.score || (1.0 - (index / (results.matches?.length || 1))),
      vector_score: match.score || (1.0 - (index / (results.matches?.length || 1))),
      metadata: match.metadata
    }));
    
  } catch (error) {
    console.error("Vector search error:", error);
    throw new Error(`Vector search failed: ${error.message}`);
  }
}

/**
 * Log search analytics for optimization
 * @param env - Cloudflare environment
 * @param projectId - Project ID
 * @param query - Search query
 * @param queryType - Type of search (keyword, semantic, hybrid)
 * @param resultCount - Number of results
 * @param latencyMs - Search latency in milliseconds
 */
export async function logSearchAnalytics(
  env: Env,
  projectId: string,
  query: string,
  queryType: 'keyword' | 'semantic' | 'hybrid',
  resultCount: number,
  latencyMs: number
): Promise<void> {
  
  try {
    await env.DB.prepare(`
      INSERT INTO search_analytics (id, project_id, query, query_type, result_count, latency_ms, created_at)
      VALUES (?, ?, ?, ?, ?, ?, ?)
    `).bind(
      crypto.randomUUID(),
      projectId,
      query,
      queryType,
      resultCount,
      latencyMs,
      Date.now()
    ).run();
    
  } catch (error) {
    console.error("Failed to log search analytics:", error);
    // Don't throw - analytics failure shouldn't break search
  }
}