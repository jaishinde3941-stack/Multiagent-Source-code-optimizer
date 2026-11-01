// Category: Concurrency Errors
// Error: Data race with shared variable

#include <iostream>
#include <thread>

int sharedCounter = 0;  // ERROR: No synchronization - data race

void increment() {
    for (int i = 0; i < 100000; i++) {
        sharedCounter++;  // Not thread-safe
    }
}

int main() {
    std::thread t1(increment);
    std::thread t2(increment);
    
    t1.join();
    t2.join();
    
    // Expected: 200000, Actual: unpredictable
    std::cout << "Counter: " << sharedCounter << std::endl;
    
    return 0;
}
