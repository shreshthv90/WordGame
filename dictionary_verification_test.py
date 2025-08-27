#!/usr/bin/env python3
"""
Focused test to verify expanded dictionary words that should be available
but weren't in the basic ~971 four-letter word dictionary mentioned by user.
"""

import sys
import os
sys.path.append('/app/backend')

from dictionary import is_valid_word, get_words_by_length

def test_expanded_dictionary():
    print("🔍 Testing Expanded Dictionary - Specific Word Verification")
    print("=" * 60)
    
    # Test some words that should be in expanded dictionary but not basic
    test_words = {
        3: ["ACE", "AGE", "AIM", "AIR", "ART", "ASK", "AXE", "BAY", "BET", "BOW"],
        4: ["ABLE", "ACID", "AGED", "AIDE", "AIMS", "AIRS", "AIRY", "AJAR", "AKIN", "ALES", 
            "ALLY", "AMID", "ANTE", "ANTI", "APEX", "ARAB", "ARCH", "ARID", "ARMY", "ARTS"],
        5: ["ABLED", "ABODE", "ABORT", "ABIDE", "ABHOR", "ABUZZ", "ACRES", "ACTED", "ACUTE", "ADDED",
            "ADMIT", "ADOPT", "ADORE", "ADULT", "AFTER", "AGAIN", "AGENT", "AGING", "AGREE", "AHEAD"],
        6: ["ACCEPT", "ACCESS", "ACCORD", "ACROSS", "ACTION", "ACTIVE", "ACTUAL", "ADJUST", "ADVICE", "ADVISE",
            "AFFECT", "AFFORD", "AFRAID", "AFRICA", "AGENCY", "AGENDA", "AGREED", "ALMOST", "ALWAYS", "AMOUNT"]
    }
    
    total_tests = 0
    passed_tests = 0
    
    for length, words in test_words.items():
        print(f"\n📚 Testing {length}-letter words:")
        
        # Get all words of this length from dictionary
        all_words = get_words_by_length(length)
        print(f"   Total {length}-letter words in dictionary: {len(all_words)}")
        
        length_passed = 0
        for word in words:
            total_tests += 1
            if is_valid_word(word, length):
                passed_tests += 1
                length_passed += 1
                print(f"   ✅ '{word}' - VALID")
            else:
                print(f"   ❌ '{word}' - INVALID")
        
        print(f"   📊 {length}-letter results: {length_passed}/{len(words)} passed")
    
    print(f"\n" + "=" * 60)
    print(f"📊 OVERALL RESULTS: {passed_tests}/{total_tests} words validated")
    success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
    print(f"📈 Success Rate: {success_rate:.1f}%")
    
    if success_rate >= 90:
        print(f"🎉 EXCELLENT! Expanded dictionary is working very well!")
        return True
    elif success_rate >= 70:
        print(f"✅ GOOD! Expanded dictionary is working well!")
        return True
    else:
        print(f"⚠️  Dictionary expansion may need attention")
        return False

def test_dictionary_size():
    print(f"\n🔢 Testing Dictionary Size:")
    
    for length in [3, 4, 5, 6]:
        words = get_words_by_length(length)
        print(f"   {length}-letter words: {len(words)}")
    
    # Test total word count
    total_words = sum(len(get_words_by_length(i)) for i in range(3, 7))
    print(f"   📊 Total words (3-6 letters): {total_words}")
    
    if total_words > 5000:
        print(f"   ✅ Dictionary size is substantial ({total_words} words)")
        return True
    else:
        print(f"   ⚠️  Dictionary size may be limited ({total_words} words)")
        return False

if __name__ == "__main__":
    success1 = test_expanded_dictionary()
    success2 = test_dictionary_size()
    
    if success1 and success2:
        print(f"\n🎉 All dictionary verification tests PASSED!")
        sys.exit(0)
    else:
        print(f"\n⚠️  Some dictionary verification tests had issues")
        sys.exit(1)