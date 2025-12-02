const express = require('express');
const cors = require('cors');
const mongoose = require('mongoose');
require('dotenv').config();

const app = express();
const PORT = process.env.PORT || 8000;

// MongoDB bağlantısı
const MONGO_URL = process.env.MONGO_URL || 'mongodb+srv://homzy_admin:<G51qubtftf>@homzy0.qj2srt7.mongodb.net/?appName=Homzy0';
const DB_NAME = process.env.DB_NAME || 'homzy';

mongoose.connect(MONGO_URL, {
  dbName: DB_NAME,
  useNewUrlParser: true,
  useUnifiedTopology: true,
})
.then(() => {
  console.log('✅ MongoDB bağlantısı başarılı!');
})
.catch((error) => {
  console.error('❌ MongoDB bağlantı hatası:', error);
});

// Middleware
app.use(cors({
  origin: ['http://localhost:3000', 'http://127.0.0.1:3000'],
  credentials: true
}));
app.use(express.json());

// MongoDB Schema
const PropertySchema = new mongoose.Schema({
  title: String,
  description: String,
  price: Number,
  currency: String,
  location: String,
  address: String,
  coordinates: {
    lat: Number,
    lng: Number
  },
  size_m2: Number,
  bedrooms: Number,
  bathrooms: Number,
  property_type: String,
  furnished: Boolean,
  pets_allowed: Boolean,
  parking: Boolean,
  balcony_garden: Boolean,
  energy_rating: String,
  availability_date: String,
  photos: [String],
  features: [String],
  country: String,
  city: String,
  featured: Boolean,
  agent_info: {
    id: String,
    name: String,
    email: String,
    picture: String
  },
  created_at: { type: Date, default: Date.now }
});

const Property = mongoose.model('Property', PropertySchema);

// Routes
app.get('/', (req, res) => {
  res.json({ 
    message: 'Homzy API is running!',
    database: 'MongoDB Connected',
    timestamp: new Date().toISOString()
  });
});

app.get('/api/properties', async (req, res) => {
  try {
    const {
      location,
      min_price,
      max_price,
      bedrooms,
      bathrooms,
      property_type,
      furnished,
      pets_allowed,
      parking,
      balcony_garden,
      country,
      featured,
      limit = 50
    } = req.query;

    // MongoDB query oluştur
    let query = {};

    if (location) {
      query.$or = [
        { location: { $regex: location, $options: 'i' } },
        { address: { $regex: location, $options: 'i' } },
        { city: { $regex: location, $options: 'i' } }
      ];
    }
    
    if (min_price) {
      query.price = { ...query.price, $gte: parseFloat(min_price) };
    }
    
    if (max_price) {
      query.price = { ...query.price, $lte: parseFloat(max_price) };
    }
    
    if (bedrooms) {
      query.bedrooms = parseInt(bedrooms);
    }
    
    if (bathrooms) {
      query.bathrooms = parseInt(bathrooms);
    }
    
    if (property_type) {
      query.property_type = property_type;
    }
    
    if (furnished !== undefined) {
      query.furnished = furnished === 'true';
    }
    
    if (pets_allowed !== undefined) {
      query.pets_allowed = pets_allowed === 'true';
    }
    
    if (parking !== undefined) {
      query.parking = parking === 'true';
    }
    
    if (balcony_garden !== undefined) {
      query.balcony_garden = balcony_garden === 'true';
    }
    
    if (country) {
      query.country = country;
    }
    
    if (featured !== undefined) {
      query.featured = featured === 'true';
    }

    const properties = await Property.find(query)
      .limit(parseInt(limit))
      .sort({ created_at: -1 });

    res.json(properties);
  } catch (error) {
    console.error('Properties fetch error:', error);
    res.status(500).json({ error: 'Veritabanı hatası' });
  }
});

app.get('/api/properties/:id', async (req, res) => {
  try {
    const property = await Property.findById(req.params.id);
    if (!property) {
      return res.status(404).json({ error: 'Property not found' });
    }
    res.json(property);
  } catch (error) {
    console.error('Property fetch error:', error);
    res.status(500).json({ error: 'Veritabanı hatası' });
  }
});

// Yeni emlak ekleme
app.post('/api/properties', async (req, res) => {
  try {
    const property = new Property(req.body);
    await property.save();
    res.status(201).json(property);
  } catch (error) {
    console.error('Property creation error:', error);
    res.status(500).json({ error: 'Emlak ekleme hatası' });
  }
});

// Emlak güncelleme
app.put('/api/properties/:id', async (req, res) => {
  try {
    const property = await Property.findByIdAndUpdate(
      req.params.id, 
      req.body, 
      { new: true }
    );
    if (!property) {
      return res.status(404).json({ error: 'Property not found' });
    }
    res.json(property);
  } catch (error) {
    console.error('Property update error:', error);
    res.status(500).json({ error: 'Emlak güncelleme hatası' });
  }
});

// Emlak silme
app.delete('/api/properties/:id', async (req, res) => {
  try {
    const property = await Property.findByIdAndDelete(req.params.id);
    if (!property) {
      return res.status(404).json({ error: 'Property not found' });
    }
    res.json({ message: 'Emlak başarıyla silindi' });
  } catch (error) {
    console.error('Property deletion error:', error);
    res.status(500).json({ error: 'Emlak silme hatası' });
  }
});

// Test verisi ekleme endpoint'i
app.post('/api/seed-data', async (req, res) => {
  try {
    // Önce mevcut verileri kontrol et
    const existingCount = await Property.countDocuments();
    if (existingCount > 0) {
      return res.json({ message: 'Veritabanında zaten veri var', count: existingCount });
    }

    const mockProperties = [
      {
        title: "Modern Apartment in Central London",
        description: "Beautiful 2-bedroom apartment in the heart of London with stunning city views.",
        price: 2500,
        currency: "GBP",
        location: "London, UK",
        address: "123 Oxford Street, London W1D 2HG",
        coordinates: { lat: 51.5074, lng: -0.1278 },
        size_m2: 85,
        bedrooms: 2,
        bathrooms: 1,
        property_type: "flat",
        furnished: true,
        pets_allowed: false,
        parking: false,
        balcony_garden: true,
        energy_rating: "B",
        availability_date: "2025-05-01",
        photos: [
          "https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?w=800",
          "https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?w=800"
        ],
        features: ["Central Heating", "Double Glazing", "Elevator"],
        country: "GB",
        city: "London",
        featured: true,
        agent_info: {
          id: "agent1",
          name: "Sarah Johnson",
          email: "sarah@homzy.com",
          picture: "https://randomuser.me/api/portraits/women/1.jpg"
        }
      },
      {
        title: "Charming Studio in Paris Marais",
        description: "Cozy studio apartment in the historic Marais district.",
        price: 1200,
        currency: "EUR",
        location: "Paris, France",
        address: "15 Rue des Rosiers, 75004 Paris",
        coordinates: { lat: 48.8566, lng: 2.3522 },
        size_m2: 35,
        bedrooms: 1,
        bathrooms: 1,
        property_type: "studio",
        furnished: true,
        pets_allowed: true,
        parking: false,
        balcony_garden: false,
        energy_rating: "C",
        availability_date: "2025-04-15",
        photos: [
          "https://images.unsplash.com/photo-1536376072261-38c75010e6c9?w=800"
        ],
        features: ["Fully Equipped Kitchen", "High-Speed WiFi"],
        country: "FR",
        city: "Paris",
        featured: true,
        agent_info: {
          id: "agent2",
          name: "Pierre Dubois",
          email: "pierre@homzy.com",
          picture: "https://randomuser.me/api/portraits/men/2.jpg"
        }
      }
    ];

    await Property.insertMany(mockProperties);
    res.json({ message: 'Test verileri başarıyla eklendi', count: mockProperties.length });
  } catch (error) {
    console.error('Seed data error:', error);
    res.status(500).json({ error: 'Test verisi ekleme hatası' });
  }
});

// Start server
app.listen(PORT, () => {
  console.log(`🚀 Server running on http://localhost:${PORT}`);
  console.log(`📊 API available at http://localhost:${PORT}/api/properties`);
  console.log(`🗄️  MongoDB: ${DB_NAME}`);
});