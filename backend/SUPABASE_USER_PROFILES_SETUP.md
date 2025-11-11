# Supabase User Profiles Setup Guide

This guide explains how to set up and use the Supabase-backed user profile system for storing user preferences and settings.

## Overview

The system has been refactored to use a dedicated `profiles` table in Supabase instead of storing everything in auth metadata or LangGraph's InMemoryStore. This provides:

- ✅ Better data organization and querying
- ✅ Row Level Security (RLS) for data protection
- ✅ Automatic profile creation on user signup
- ✅ Flexible JSONB preferences storage
- ✅ Proper database relationships and constraints

## 1. Database Setup

### Prerequisites
- Supabase project created
- Database access via Supabase dashboard or SQL editor

### Migration Applied
The following migration has been applied to create the profiles table:

```sql
-- Create profiles table for user preferences and settings
create table public.profiles (
  id uuid not null references auth.users on delete cascade primary key,
  created_at timestamp with time zone default timezone('utc'::text, now()) not null,
  updated_at timestamp with time zone default timezone('utc'::text, now()) not null,
  
  -- Basic profile information
  name text,
  email text,
  
  -- LLM preferences
  llm_provider text default 'openai' check (llm_provider in ('openai', 'ollama', 'deepseek', 'groq')),
  llm_model text default 'gpt-4o-mini',
  
  -- Communication preferences
  communication_style text default 'balanced' check (communication_style in ('concise', 'detailed', 'balanced')),
  
  -- Additional preferences as JSONB for flexibility
  preferences jsonb default '{}'::jsonb
);

-- Set up Row Level Security (RLS)
alter table public.profiles enable row level security;

-- RLS Policies - users can only access their own profiles
create policy "Users can view their own profiles" 
  on public.profiles for select 
  using (auth.uid() = id);

create policy "Users can update their own profiles" 
  on public.profiles for update 
  using (auth.uid() = id);

create policy "Users can insert their own profiles" 
  on public.profiles for insert 
  with check (auth.uid() = id);

-- Auto-update timestamp trigger
create or replace function public.handle_updated_at()
returns trigger as $$
begin
  new.updated_at = timezone('utc'::text, now());
  return new;
end;
$$ language plpgsql;

create trigger handle_profiles_updated_at
  before update on public.profiles
  for each row
  execute function public.handle_updated_at();

-- Auto-create profile on user signup
create or replace function public.handle_new_user()
returns trigger as $$
begin
  insert into public.profiles (id, email, name)
  values (
    new.id, 
    new.email,
    coalesce(new.raw_user_meta_data->>'full_name', new.raw_user_meta_data->>'name', 'User')
  );
  return new;
end;
$$ language plpgsql security definer;

create trigger on_auth_user_created
  after insert on auth.users
  for each row
  execute function public.handle_new_user();
```

## 2. Environment Configuration

Add these environment variables to your backend:

```bash
# Required for Supabase integration
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key

# Optional: JWT secret for token verification (production)
SUPABASE_JWT_SECRET=your-jwt-secret
```

### Getting Your Credentials

1. **SUPABASE_URL**: Found in your Supabase project settings → API
2. **SUPABASE_SERVICE_ROLE_KEY**: Found in your Supabase project settings → API → service_role key
3. **SUPABASE_JWT_SECRET**: Found in your Supabase project settings → API → JWT Settings

## 3. Code Integration

### UserMemoryService

The `UserMemoryService` has been completely refactored to use the Supabase profiles table:

```python
from src.services.user_memory_service import get_user_memory_service

# Get the service (singleton)
memory_service = get_user_memory_service()

# Check if properly configured
if memory_service.is_configured:
    print("✅ Supabase integration ready")
else:
    print("❌ Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")
```

### Profile Tools

The profile tools automatically check for Supabase configuration:

```python
from src.tools.profile_tools import get_profile_tools

# All tools will return helpful error messages if not configured
tools = get_profile_tools()
```

## 4. Usage Examples

### Saving User Preferences

```python
# Save a user preference
success = memory_service.update_user_preference(
    user_id="user-uuid-here",
    preference_key="theme",
    preference_value="dark"
)

# Save LLM preferences
success = memory_service.update_llm_config(
    user_id="user-uuid-here",
    llm_provider="openai",
    llm_model="gpt-4o"
)

# Save full profile
success = memory_service.save_user_profile(
    user_id="user-uuid-here",
    name="John Doe",
    email="john@example.com",
    llm_provider="openai",
    llm_model="gpt-4o-mini",
    communication_style="detailed",
    preferences={"theme": "dark", "notifications": True}
)
```

### Retrieving User Profiles

```python
# Get user profile
profile = memory_service.get_user_profile("user-uuid-here")

if profile:
    print(f"Name: {profile['name']}")
    print(f"LLM: {profile['llm_provider']}/{profile['llm_model']}")
    print(f"Style: {profile['communication_style']}")
    print(f"Preferences: {profile['preferences']}")
```

### Using Profile Tools (Agent Context)

The profile tools work within the LangGraph agent context:

```python
# These tools automatically get user_id from the agent config
save_user_preference("theme", "dark")
update_user_name("John Doe")
update_communication_style("concise")
update_llm_preference("openai", "gpt-4o")
get_user_profile()
```

## 5. Database Schema

### profiles Table Structure

| Column | Type | Description |
|--------|------|-------------|
| `id` | uuid | Primary key, references auth.users |
| `created_at` | timestamptz | Auto-set on creation |
| `updated_at` | timestamptz | Auto-updated on changes |
| `name` | text | User's display name |
| `email` | text | User's email address |
| `llm_provider` | text | AI provider (openai, ollama, deepseek, groq) |
| `llm_model` | text | Specific model name |
| `communication_style` | text | Style preference (concise, detailed, balanced) |
| `preferences` | jsonb | Flexible JSON storage for additional preferences |

### Row Level Security

- Users can only access their own profiles
- Automatic profile creation on user signup
- Secure service-role access for backend operations

## 6. Migration from LangGraph Store

If you were previously using LangGraph's InMemoryStore:

1. ✅ **Automatic**: The new service maintains the same interface
2. ✅ **Backward Compatible**: Old method signatures still work
3. ✅ **Graceful Fallback**: Returns helpful errors if not configured
4. ⚠️ **Data Migration**: Existing in-memory data will be lost (expected)

## 7. Troubleshooting

### Common Issues

1. **"Supabase credentials are not configured"**
   - Check environment variables are set correctly
   - Verify SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY

2. **"Profile for user X not found"**
   - User might not have signed up through Supabase Auth
   - Check if the trigger `on_auth_user_created` is working

3. **"Row Level Security policy violation"**
   - Make sure you're using the service role key, not anon key
   - Verify RLS policies are correctly set up

### Debugging

Enable debug logging:

```python
import logging
logging.getLogger('src.services.user_memory_service').setLevel(logging.DEBUG)
```

### Manual Profile Creation

If needed, you can manually create a profile:

```sql
INSERT INTO public.profiles (id, name, email)
VALUES ('user-uuid-here', 'User Name', 'user@example.com');
```

## 8. Security Considerations

- ✅ Service role key is used for backend operations
- ✅ RLS policies prevent unauthorized access
- ✅ Preferences are stored as JSONB for flexibility but type safety
- ✅ Foreign key constraints ensure data integrity
- ✅ Automatic cleanup when users are deleted

## 9. Future Enhancements

Possible improvements:

- Add more structured preference fields
- Implement preference versioning
- Add preference sharing/templates
- Integrate with Supabase Realtime for live updates
- Add preference validation schemas

---

## Summary

The user profile system is now fully integrated with Supabase, providing:

- ✅ Persistent storage in a proper database
- ✅ Row-level security for data protection  
- ✅ Automatic profile creation and management
- ✅ Flexible preference storage with JSONB
- ✅ Backward compatibility with existing code
- ✅ Proper error handling and configuration checks

Your agent can now remember user preferences across sessions and provide personalized experiences!
