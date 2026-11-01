// Category: Concurrency Errors (Success Case)
// Expected Result: Use atomic variables or mutexes for shared data

#include <iostream>
#include <thread>
#include <atomic>

// SUCCESS: Used atomic counter to prevent data race
std::atomic<int> sharedCounter(0);

void increment() {
    for (int i = 0; i < 100000; i++) {
        sharedCounter++;  // Atomic increment
    }
}

int main() {
    std::thread t1(increment);
    std::thread t2(increment);
    
    t1.join();
    t2.join();
    
    std::cout << "Counter: " << sharedCounter.load() << std::endl;
    
    return 0;
}
