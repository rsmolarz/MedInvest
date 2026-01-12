/**
 * Database Seed Script
 * Run: npm run db:seed
 */

import { PrismaClient } from '@prisma/client';
import bcrypt from 'bcryptjs';

const prisma = new PrismaClient();

async function main() {
  console.log('🌱 Seeding database...');
  
  // Create rooms
  const rooms = await Promise.all([
    prisma.room.upsert({
      where: { slug: 'cardiology' },
      update: {},
      create: {
        name: 'Cardiology',
        slug: 'cardiology',
        description: 'Discussions about cardiovascular medicine, heart disease, and cardiac procedures.',
        icon: '❤️',
        color: '#EF4444',
        is_default: true,
      },
    }),
    prisma.room.upsert({
      where: { slug: 'oncology' },
      update: {},
      create: {
        name: 'Oncology',
        slug: 'oncology',
        description: 'Cancer research, treatment advances, and oncological care.',
        icon: '🎗️',
        color: '#8B5CF6',
        is_default: true,
      },
    }),
    prisma.room.upsert({
      where: { slug: 'neurology' },
      update: {},
      create: {
        name: 'Neurology',
        slug: 'neurology',
        description: 'Brain and nervous system disorders, neuroscience research.',
        icon: '🧠',
        color: '#EC4899',
        is_default: true,
      },
    }),
    prisma.room.upsert({
      where: { slug: 'digital-health' },
      update: {},
      create: {
        name: 'Digital Health',
        slug: 'digital-health',
        description: 'Healthcare technology, telemedicine, and health tech startups.',
        icon: '💻',
        color: '#3B82F6',
        is_default: true,
      },
    }),
    prisma.room.upsert({
      where: { slug: 'biotech' },
      update: {},
      create: {
        name: 'Biotech',
        slug: 'biotech',
        description: 'Biotechnology companies, drug development, and clinical trials.',
        icon: '🧬',
        color: '#10B981',
        is_default: true,
      },
    }),
    prisma.room.upsert({
      where: { slug: 'medical-devices' },
      update: {},
      create: {
        name: 'Medical Devices',
        slug: 'medical-devices',
        description: 'Medical device innovation, FDA approvals, and device companies.',
        icon: '🔬',
        color: '#F59E0B',
        is_default: true,
      },
    }),
    prisma.room.upsert({
      where: { slug: 'healthcare-investing' },
      update: {},
      create: {
        name: 'Healthcare Investing',
        slug: 'healthcare-investing',
        description: 'Investment strategies, market analysis, and deal flow in healthcare.',
        icon: '📈',
        color: '#6366F1',
        is_default: true,
      },
    }),
    prisma.room.upsert({
      where: { slug: 'general' },
      update: {},
      create: {
        name: 'General',
        slug: 'general',
        description: 'General healthcare discussions and community updates.',
        icon: '💬',
        color: '#6B7280',
        is_default: true,
      },
    }),
  ]);
  
  console.log(`✅ Created ${rooms.length} rooms`);
  
  // Create demo user
  const hashedPassword = await bcrypt.hash('Demo123!', 12);
  
  const demoUser = await prisma.user.upsert({
    where: { email: 'demo@medinvest.com' },
    update: {},
    create: {
      email: 'demo@medinvest.com',
      password: hashedPassword,
      full_name: 'Demo User',
      username: 'demo',
      bio: 'Demo account for testing MedInvest',
      specialty: 'Healthcare Technology',
      is_verified: true,
      email_verified: true,
      email_verified_at: new Date(),
    },
  });
  
  console.log(`✅ Created demo user: demo@medinvest.com / Demo123!`);
  
  // Create demo user settings
  await prisma.userSettings.upsert({
    where: { user_id: demoUser.id },
    update: {},
    create: { user_id: demoUser.id },
  });
  
  // Create sample deals
  const deals = await Promise.all([
    prisma.deal.upsert({
      where: { id: 1 },
      update: {},
      create: {
        title: 'AI-Powered Diagnostic Platform',
        company_name: 'MedAI Diagnostics',
        description: 'Revolutionary AI platform that can detect early-stage cancers from routine blood tests with 95% accuracy. Currently in Phase 2 clinical trials.',
        sector: 'Digital Health',
        stage: 'series_a',
        minimum_investment: 25000,
        target_raise: 15000000,
        current_raise: 8500000,
        valuation: 75000000,
        is_featured: true,
      },
    }),
    prisma.deal.upsert({
      where: { id: 2 },
      update: {},
      create: {
        title: 'Next-Gen Insulin Delivery',
        company_name: 'GlucoTech',
        description: 'Smart insulin pump with closed-loop AI system that automatically adjusts insulin delivery based on real-time glucose monitoring.',
        sector: 'Medical Devices',
        stage: 'series_b',
        minimum_investment: 50000,
        target_raise: 30000000,
        current_raise: 12000000,
        valuation: 150000000,
        is_featured: true,
      },
    }),
    prisma.deal.upsert({
      where: { id: 3 },
      update: {},
      create: {
        title: 'Gene Therapy for Rare Diseases',
        company_name: 'GeneCure Bio',
        description: 'Developing breakthrough gene therapies for rare pediatric diseases. Lead candidate has shown remarkable results in early trials.',
        sector: 'Biotech',
        stage: 'seed',
        minimum_investment: 10000,
        target_raise: 5000000,
        current_raise: 2100000,
        valuation: 20000000,
        is_featured: false,
      },
    }),
  ]);
  
  console.log(`✅ Created ${deals.length} sample deals`);
  
  // Create achievements
  const achievements = await Promise.all([
    prisma.achievement.upsert({
      where: { slug: 'first-post' },
      update: {},
      create: {
        slug: 'first-post',
        name: 'First Steps',
        description: 'Published your first post',
        icon: '✍️',
        points: 10,
      },
    }),
    prisma.achievement.upsert({
      where: { slug: 'verified' },
      update: {},
      create: {
        slug: 'verified',
        name: 'Verified Professional',
        description: 'Completed professional verification',
        icon: '✅',
        points: 100,
      },
    }),
    prisma.achievement.upsert({
      where: { slug: 'first-investment' },
      update: {},
      create: {
        slug: 'first-investment',
        name: 'Investor',
        description: 'Made your first investment',
        icon: '💰',
        points: 50,
      },
    }),
    prisma.achievement.upsert({
      where: { slug: 'community-builder' },
      update: {},
      create: {
        slug: 'community-builder',
        name: 'Community Builder',
        description: 'Reached 100 followers',
        icon: '🌟',
        points: 75,
      },
    }),
  ]);
  
  console.log(`✅ Created ${achievements.length} achievements`);
  
  // Create some hashtags
  const hashtags = await Promise.all([
    prisma.hashtag.upsert({
      where: { tag: 'healthtech' },
      update: {},
      create: { tag: 'healthtech', posts_count: 0 },
    }),
    prisma.hashtag.upsert({
      where: { tag: 'medtech' },
      update: {},
      create: { tag: 'medtech', posts_count: 0 },
    }),
    prisma.hashtag.upsert({
      where: { tag: 'biotech' },
      update: {},
      create: { tag: 'biotech', posts_count: 0 },
    }),
    prisma.hashtag.upsert({
      where: { tag: 'digitalhealth' },
      update: {},
      create: { tag: 'digitalhealth', posts_count: 0 },
    }),
    prisma.hashtag.upsert({
      where: { tag: 'healthcare' },
      update: {},
      create: { tag: 'healthcare', posts_count: 0 },
    }),
  ]);
  
  console.log(`✅ Created ${hashtags.length} hashtags`);
  
  console.log('');
  console.log('🎉 Database seeded successfully!');
  console.log('');
  console.log('Demo credentials:');
  console.log('  Email: demo@medinvest.com');
  console.log('  Password: Demo123!');
}

main()
  .catch((e) => {
    console.error('❌ Seed failed:', e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
